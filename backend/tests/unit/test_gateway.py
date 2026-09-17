"""LLMGateway route walking, recording, budget, search and embeddings (FunctionModel only, no network)."""

import pickle
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import httpx
import httpx2
import pytest
from pydantic import BaseModel, SecretStr
from pydantic_ai import ModelResponse, RequestUsage, ToolCallPart, models
from pydantic_ai.exceptions import ModelAPIError, ModelHTTPError
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.openai import OpenAIProvider

from mdcopilot_blog.domain.enums import AgentName, CallKind, CallStatus
from mdcopilot_blog.ids import new_trace_id, uuid7
from mdcopilot_blog.llm.gateway import (
    AgentResult,
    AgentSpec,
    BudgetExceeded,
    CallContext,
    LLMGateway,
    ModelFactory,
    ProviderNotAvailable,
    RouteExhausted,
    UnavailableModelFactory,
    UnavailableSearchProvider,
    build_model_factory,
)
from mdcopilot_blog.llm.mock import FixtureRegistry, MockModelFactory
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder
from mdcopilot_blog.llm.routes import ModelChoice
from mdcopilot_blog.llm.search.base import SearchQuery
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider
from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root
from mdcopilot_blog.settings import Settings

FunctionDef = Callable[[list[ModelMessage], AgentInfo], ModelResponse]


class Draft(BaseModel):
    title: str
    words: int


class EchoOut(BaseModel):
    message: str
    word_count: int


WRITER_SPEC = AgentSpec(
    name=AgentName.WRITER,
    version="1",
    prompt_name="writer/draft",
    output_type=Draft,
    max_output_tokens=300,
    output_retries=1,
)


class FakeRecorder(CallRecorder):
    """In-memory recorder. ``cost_per_error`` simulates spend recorded by failed attempts."""

    def __init__(self, *, cost: Decimal = Decimal(0), cost_per_error: Decimal = Decimal(0)) -> None:
        self.records: list[CallRecord] = []
        self.cost = cost
        self.cost_per_error = cost_per_error
        self.cost_queries: list[Any] = []

    async def record(self, rec: CallRecord) -> Any:
        self.records.append(rec)
        if rec.status == CallStatus.ERROR:
            self.cost += self.cost_per_error
        return uuid7()

    async def run_cost(self, run_id: Any) -> Decimal:
        self.cost_queries.append(run_id)
        return self.cost if run_id is not None else Decimal(0)


@dataclass
class ScriptedFactory(ModelFactory):
    """Maps a route ref ("openai:model-a") to a model builder and remembers what was built."""

    scripts: dict[str, Callable[[], Model]]
    built: list[str] = field(default_factory=list)

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        self.built.append(choice.ref())
        return self.scripts[choice.ref()]()


def ok(model_name: str, payload: dict[str, Any], seen: list[AgentInfo] | None = None) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        if seen is not None:
            seen.append(info)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, payload)],
            usage=RequestUsage(input_tokens=50, output_tokens=12),
        )

    return lambda: FunctionModel(respond, model_name=model_name)


def failing(model_name: str, exc: Exception) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise exc

    return lambda: FunctionModel(respond, model_name=model_name)


def invalid(model_name: str, calls: list[int]) -> Callable[[], Model]:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        calls.append(1)
        return ModelResponse(
            parts=[ToolCallPart(info.output_tools[0].name, {"title": "t", "words": "not-a-number"})],
            usage=RequestUsage(input_tokens=10, output_tokens=3),
        )

    return lambda: FunctionModel(respond, model_name=model_name)


@pytest.fixture
def prompts(tmp_path: Path) -> PromptRegistry:
    path = tmp_path / "writer" / "draft.v1.md"
    path.parent.mkdir(parents=True)
    path.write_text(
        "---\nname: writer/draft\nversion: 1\nagent: writer\noutput: Draft\nvariables:\n  - topic\n---\n"
        "Write about {{ topic }}.\n",
        encoding="utf-8",
    )
    return PromptRegistry.from_directory(tmp_path)


@pytest.fixture
def gw_settings(settings: Settings) -> Settings:
    return settings.model_copy(
        update={
            "mock_mode": True,
            "writer_route": ["openai:model-a", "google:model-b"],
            "max_cost_per_run_usd": Decimal("1.00"),
            "embedding_model": "google:gemini-embedding-test",
            "embedding_dimensions": 8,
        }
    )


@pytest.fixture
def ctx() -> CallContext:
    return CallContext(trace_id=new_trace_id(), run_id=uuid7(), attempt_id=uuid7(), dbos_workflow_id="wf-1")


def make_gateway(
    settings: Settings,
    prompts: PromptRegistry,
    factory: ModelFactory,
    recorder: FakeRecorder,
    search_provider: Any | None = None,
) -> LLMGateway:
    return LLMGateway(
        settings=settings,
        prompts=prompts,
        recorder=recorder,
        model_factory=factory,
        search_provider=search_provider or FixtureSearchProvider(),
    )


async def test_success_records_one_ok_row(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    seen: list[AgentInfo] = []
    factory = ScriptedFactory({"openai:model-a": ok("fixture-a", {"title": "Hello", "words": 2}, seen)})
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, factory, recorder)

    result = await gateway.run(WRITER_SPEC, variables={"topic": "burnout"}, user_prompt="Go.", ctx=ctx)

    assert isinstance(result, AgentResult)
    assert result.output == Draft(title="Hello", words=2)
    assert (result.model, result.attempts) == ("fixture-a", 1)
    assert (result.input_tokens, result.output_tokens, result.cost_usd) == (50, 12, Decimal(0))
    assert factory.built == ["openai:model-a"]

    assert seen[0].instructions == "Write about burnout."  # pydantic-ai strips surrounding whitespace
    assert seen[0].model_settings is not None
    assert seen[0].model_settings.get("max_tokens") == 300
    assert seen[0].model_settings.get("timeout") == 120.0

    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.kind == CallKind.AGENT
    assert rec.status == CallStatus.OK
    assert rec.ctx == ctx
    assert (rec.provider_requested, rec.model_requested) == ("openai", "model-a")
    assert (rec.provider_served, rec.model_served) == ("function", "fixture-a")
    assert rec.attempt_index == 0
    assert rec.fallback_from is None
    assert rec.agent_name == "writer"
    assert (rec.prompt_name, rec.prompt_version) == ("writer/draft", 1)
    assert rec.prompt_sha == prompts.get("writer/draft").sha256
    assert (rec.input_tokens, rec.output_tokens) == (50, 12)
    assert rec.params == {"max_tokens": 300, "timeout": 120.0, "output_retries": 1, "agent_version": "1"}
    assert rec.error_class is None
    assert rec.usage_raw["requests"] == [
        {
            "model_name": "fixture-a",
            "provider_name": None,
            "input_tokens": 50,
            "output_tokens": 12,
            "cache_read_tokens": 0,
            "cache_write_tokens": 0,
            "reasoning_tokens": 0,
            "details": {},
            "cost": None,
        }
    ]
    assert recorder.cost_queries == [ctx.run_id]


async def test_http_503_falls_back_to_next_model(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing(
                "fixture-a", ModelHTTPError(status_code=503, model_name="model-a", body={"error": "overloaded"})
            ),
            "google:model-b": ok("fixture-b", {"title": "Fallback", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, factory, recorder)

    result = await gateway.run(WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx)

    assert result.output.title == "Fallback"
    assert result.attempts == 2
    assert result.model == "fixture-b"
    assert factory.built == ["openai:model-a", "google:model-b"]

    first, second = recorder.records
    assert (first.status, first.error_class, first.attempt_index, first.fallback_from) == (
        CallStatus.ERROR,
        "ModelHTTPError",
        0,
        None,
    )
    assert first.error_message is not None
    assert "503" in first.error_message
    assert (first.provider_requested, first.model_requested) == ("openai", "model-a")
    assert (second.status, second.attempt_index, second.fallback_from) == (CallStatus.OK, 1, "openai:model-a")
    assert (second.provider_requested, second.model_requested) == ("google", "model-b")
    assert recorder.cost_queries == [ctx.run_id, ctx.run_id]  # budget checked before each model call


@pytest.mark.parametrize(
    "exc",
    [
        ModelAPIError(model_name="model-a", message="Connection error."),
        httpx2.ConnectError("connection refused"),
        httpx2.ReadTimeout("read timed out"),
        httpx.ConnectError("connection refused"),
    ],
    ids=["model-api-error", "httpx2-connect", "httpx2-timeout", "httpx-connect"],
)
async def test_transport_errors_advance_the_route(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext, exc: Exception
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", exc),
            "google:model-b": ok("fixture-b", {"title": "B", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    result = await make_gateway(gw_settings, prompts, factory, recorder).run(
        WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
    )
    assert result.attempts == 2
    assert [r.error_class for r in recorder.records] == [type(exc).__name__, None]


async def test_invalid_output_exhausts_retries_then_advances(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    calls: list[int] = []
    factory = ScriptedFactory(
        {
            "openai:model-a": invalid("fixture-a", calls),
            "google:model-b": ok("fixture-b", {"title": "Valid", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    result = await make_gateway(gw_settings, prompts, factory, recorder).run(
        WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
    )

    assert result.output.title == "Valid"
    assert len(calls) == WRITER_SPEC.output_retries + 1
    failed = recorder.records[0]
    assert failed.status == CallStatus.ERROR
    assert failed.error_class == "UnexpectedModelBehavior"
    assert failed.model_served == "fixture-a"
    assert (failed.input_tokens, failed.output_tokens) == (20, 6)  # both failed requests are accounted
    assert recorder.records[1].fallback_from == "openai:model-a"


async def test_all_models_fail_raises_route_exhausted(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ModelHTTPError(status_code=503, model_name="model-a")),
            "google:model-b": failing("fixture-b", ModelAPIError(model_name="model-b", message="Request timed out.")),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(RouteExhausted) as caught:
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )

    assert caught.value.failures == [("openai:model-a", "ModelHTTPError"), ("google:model-b", "ModelAPIError")]
    assert "writer" in str(caught.value)
    assert [(r.status, r.attempt_index, r.fallback_from) for r in recorder.records] == [
        (CallStatus.ERROR, 0, None),
        (CallStatus.ERROR, 1, "openai:model-a"),
    ]


def test_route_exhausted_survives_pickle() -> None:
    original = RouteExhausted("writer", [("openai:model-a", "ModelHTTPError")])
    restored = pickle.loads(pickle.dumps(original))
    assert isinstance(restored, RouteExhausted)
    assert restored.failures == original.failures
    assert str(restored) == str(original)


async def test_budget_exceeded_blocks_before_any_call(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory({"openai:model-a": ok("fixture-a", {"title": "t", "words": 1})})
    recorder = FakeRecorder(cost=Decimal("1.00"))
    with pytest.raises(BudgetExceeded, match="cap is 1.00 USD"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == []
    assert recorder.records == []


async def test_budget_is_rechecked_before_a_fallback(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ModelHTTPError(status_code=500, model_name="model-a")),
            "google:model-b": ok("fixture-b", {"title": "t", "words": 1}),
        }
    )
    recorder = FakeRecorder(cost_per_error=Decimal("1.50"))
    with pytest.raises(BudgetExceeded):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert len(recorder.records) == 1


async def test_allow_model_requests_error_is_reraised_not_advanced(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", False)
    factory = ScriptedFactory(
        {
            # a real model class: with ALLOW_MODEL_REQUESTS False it raises before any HTTP request
            "openai:model-a": lambda: OpenAIChatModel("gpt-test", provider=OpenAIProvider(api_key="sk-test")),
            "google:model-b": ok("fixture-b", {"title": "never", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(RuntimeError, match="ALLOW_MODEL_REQUESTS"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert len(recorder.records) == 1
    assert recorder.records[0].status == CallStatus.ERROR
    assert recorder.records[0].error_class == "RuntimeError"
    assert recorder.records[0].provider_served == "openai"


async def test_unexpected_exception_is_recorded_and_reraised(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    factory = ScriptedFactory(
        {
            "openai:model-a": failing("fixture-a", ValueError("bug in fixture")),
            "google:model-b": ok("fixture-b", {"title": "never", "words": 1}),
        }
    )
    recorder = FakeRecorder()
    with pytest.raises(ValueError, match="bug in fixture"):
        await make_gateway(gw_settings, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert factory.built == ["openai:model-a"]
    assert [(r.status, r.error_class) for r in recorder.records] == [(CallStatus.ERROR, "ValueError")]


async def test_real_mode_factory_is_unavailable(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    real = gw_settings.model_copy(
        update={
            "mock_mode": False,
            "openai_api_key": SecretStr("sk-test"),
            "gemini_api_key": SecretStr("gm-test"),
        }
    )
    factory = build_model_factory(real)
    assert isinstance(factory, UnavailableModelFactory)
    recorder = FakeRecorder()
    with pytest.raises(ProviderNotAvailable, match="Phase 2"):
        await make_gateway(real, prompts, factory, recorder).run(
            WRITER_SPEC, variables={"topic": "x"}, user_prompt="Go.", ctx=ctx
        )
    assert [(r.status, r.error_class) for r in recorder.records] == [(CallStatus.ERROR, "ProviderNotAvailable")]


def test_mock_mode_factory_disables_real_requests(gw_settings: Settings, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)
    factory = build_model_factory(gw_settings)
    assert isinstance(factory, MockModelFactory)
    assert models.ALLOW_MODEL_REQUESTS is False


async def test_mock_gateway_runs_hello_fixture_end_to_end(
    gw_settings: Settings, ctx: CallContext, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(models, "ALLOW_MODEL_REQUESTS", True)
    recorder = FakeRecorder()
    gateway = make_gateway(
        gw_settings,
        PromptRegistry.from_directory(default_prompt_root()),
        build_model_factory(gw_settings),
        recorder,
    )
    spec = AgentSpec(
        name=AgentName.HELLO, version="1", prompt_name="hello/echo", output_type=EchoOut, max_output_tokens=200
    )

    result = await gateway.run(
        spec, variables={"brand_name": "MDCopilot", "topic": "hello"}, user_prompt="Say hello.", ctx=ctx
    )

    assert result.output == EchoOut(message="Hello from the mock gateway", word_count=5)
    assert (result.model, result.attempts, result.input_tokens, result.output_tokens) == ("mock:hello", 1, 20, 8)
    rec = recorder.records[0]
    assert (rec.provider_requested, rec.model_requested, rec.model_served) == ("mock", "hello", "mock:hello")
    assert rec.prompt_name == "hello/echo"


def test_fixture_registry_reports_missing_and_malformed_files(tmp_path: Path) -> None:
    registry = FixtureRegistry(tmp_path)
    with pytest.raises(FileNotFoundError, match=r"no mock fixture for agent 'writer' prompt 'writer/draft'"):
        registry.load("writer", "writer/draft")

    bad = tmp_path / "writer" / "writer_draft.json"
    bad.parent.mkdir(parents=True)
    bad.write_text('{"output": {"title": "t"}, "usage": {"input_tokens": 1}}', encoding="utf-8")
    with pytest.raises(ValueError, match="'usage' must be"):
        registry.load("writer", "writer/draft")


def test_default_fixture_registry_has_hello_echo() -> None:
    fixture = FixtureRegistry.default().load("hello", "hello/echo")
    assert fixture == {
        "output": {"message": "Hello from the mock gateway", "word_count": 5},
        "usage": {"input_tokens": 20, "output_tokens": 8},
    }


async def test_search_records_a_search_row(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder, FixtureSearchProvider())

    result = await gateway.search(SearchQuery(text="specialist access"), ctx=ctx)

    assert result.answer_text.startswith("[fixture] specialist access: ")
    assert len(recorder.records) == 1
    rec = recorder.records[0]
    assert rec.kind == CallKind.SEARCH
    assert rec.status == CallStatus.OK
    assert (rec.provider_requested, rec.model_requested) == ("fixture", "fixture")
    assert (rec.provider_served, rec.model_served) == ("fixture", "fixture-search")
    assert rec.search_actions == result.search_actions == 1
    assert rec.agent_name == "search"
    assert rec.params["text"] == "specialist access"
    assert rec.ctx == ctx
    assert recorder.cost_queries == [ctx.run_id]


async def test_search_failure_is_recorded_and_reraised(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder, UnavailableSearchProvider())
    with pytest.raises(ProviderNotAvailable):
        await gateway.search(SearchQuery(text="q"), ctx=ctx)
    assert [(r.kind, r.status, r.error_class) for r in recorder.records] == [
        (CallKind.SEARCH, CallStatus.ERROR, "ProviderNotAvailable")
    ]


async def test_search_respects_budget(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder(cost=Decimal(2))
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder)
    with pytest.raises(BudgetExceeded):
        await gateway.search(SearchQuery(text="q"), ctx=ctx)
    assert recorder.records == []


async def test_embed_is_deterministic_in_mock_mode(
    gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext
) -> None:
    recorder = FakeRecorder()
    gateway = make_gateway(gw_settings, prompts, ScriptedFactory({}), recorder)

    first = await gateway.embed(["alpha topic", "beta topic"], ctx=ctx)
    second = await gateway.embed(["alpha topic"], ctx=ctx)

    assert len(first) == 2
    assert all(len(vector) == 8 for vector in first)
    assert all(-1.0 <= value <= 1.0 for vector in first for value in vector)
    assert first[0] == second[0]
    assert first[0] != first[1]

    assert len(recorder.records) == 2
    rec = recorder.records[0]
    assert rec.kind == CallKind.EMBEDDING
    assert rec.status == CallStatus.OK
    assert (rec.provider_requested, rec.model_requested) == ("google", "gemini-embedding-test")
    assert (rec.provider_served, rec.model_served) == ("mock", "mock:embedding")
    assert rec.params == {"dimensions": 8, "count": 2}
    assert rec.input_tokens == 4


async def test_embed_requires_mock_mode(gw_settings: Settings, prompts: PromptRegistry, ctx: CallContext) -> None:
    recorder = FakeRecorder()
    real = gw_settings.model_copy(update={"mock_mode": False})
    gateway = make_gateway(real, prompts, ScriptedFactory({}), recorder)
    with pytest.raises(ProviderNotAvailable):
        await gateway.embed(["alpha"], ctx=ctx)
    assert recorder.records == []
