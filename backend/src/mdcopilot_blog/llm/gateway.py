"""LLM gateway: every model, web-search and embedding call goes through here (ARCHITECTURE §7.1).

``run()`` walks the configured route itself (no FallbackModel). Each attempt writes exactly one
``blog_llm_calls`` row. Phase 1 builds mock models only; real providers arrive in Phase 2.
"""

import hashlib
import random
import time
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Protocol

import httpx
import httpx2
from pydantic import BaseModel
from pydantic_ai import Agent, ModelResponse, capture_run_messages, models
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.domain.enums import AgentName, CallKind, CallStatus
from mdcopilot_blog.llm.recorder import CallRecord, CallRecorder
from mdcopilot_blog.llm.routes import ModelChoice, parse_choice, route_for
from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult, WebSearchProvider
from mdcopilot_blog.llm.search.fixture import FixtureSearchProvider
from mdcopilot_blog.prompts.registry import PromptRegistry, RenderedPrompt
from mdcopilot_blog.settings import Settings

# Errors that move the route to its next model. Google leaks raw httpx2 transport errors;
# httpx.TransportError is caught for safety. Everything else is recorded and re-raised,
# including UsageLimitExceeded and the plain RuntimeError raised when ALLOW_MODEL_REQUESTS is False.
ADVANCE_ERRORS: tuple[type[Exception], ...] = (
    ModelAPIError,
    UnexpectedModelBehavior,
    httpx.TransportError,
    httpx2.TransportError,
)

MOCK_EMBEDDING_PROVIDER = "mock"
MOCK_EMBEDDING_MODEL = "mock:embedding"


@dataclass(frozen=True)
class AgentSpec[OutputT: BaseModel]:
    name: AgentName
    version: str
    prompt_name: str
    output_type: type[OutputT]
    max_output_tokens: int
    output_retries: int = 1
    timeout_seconds: float = 120.0


@dataclass(frozen=True)
class CallContext:
    trace_id: str
    run_id: uuid.UUID | None = None
    attempt_id: uuid.UUID | None = None
    agent_run_id: uuid.UUID | None = None
    dbos_workflow_id: str | None = None
    dbos_step_id: int | None = None
    article_id: uuid.UUID | None = None
    topic_candidate_id: uuid.UUID | None = None


@dataclass(frozen=True)
class AgentResult[OutputT: BaseModel]:
    output: OutputT
    provider: str
    model: str
    attempts: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


class GatewayError(RuntimeError):
    """Base class for gateway failures."""


class BudgetExceeded(GatewayError):
    """The run already spent its per-run cost cap."""


class RouteExhausted(GatewayError):
    """Every model in the route failed with a route-advancing error."""

    def __init__(self, agent: str, failures: Sequence[tuple[str, str]]) -> None:
        self.agent = agent
        self.failures: list[tuple[str, str]] = list(failures)
        summary = ", ".join(f"{ref} ({error_class})" for ref, error_class in self.failures)
        super().__init__(f"all models failed for agent {agent!r}: {summary}")

    def __reduce__(self) -> tuple[Any, ...]:
        # keeps the exception picklable (DBOS serialises step errors)
        return (self.__class__, (self.agent, self.failures))


class ProviderNotAvailable(GatewayError):
    """A real provider was requested but is not built or not allowed."""


class ModelFactory(Protocol):
    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model: ...


class UnavailableModelFactory(ModelFactory):
    """Used when mock mode is off. Real model construction lands in Phase 2."""

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        raise ProviderNotAvailable("real providers are enabled in Phase 2")


class UnavailableSearchProvider:
    """Used when mock mode is off. Real search providers land in Phase 2."""

    name = "unavailable"

    async def search(self, query: SearchQuery) -> SearchResult:
        raise ProviderNotAvailable("real search providers are enabled in Phase 2")


@dataclass(frozen=True)
class _Usage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    reasoning_tokens: int
    cost_usd: Decimal
    model_served: str | None
    provider_served: str | None
    raw: dict[str, object]


def _sum_usage(messages: Sequence[ModelMessage]) -> _Usage:
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    requests: list[dict[str, object]] = []
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "reasoning": 0}
    cost = Decimal(0)
    for response in responses:
        usage = response.usage
        reasoning = int(getattr(usage, "output_reasoning_tokens", 0) or 0)
        totals["input"] += usage.input_tokens
        totals["output"] += usage.output_tokens
        totals["cache_read"] += usage.cache_read_tokens
        totals["cache_write"] += usage.cache_write_tokens
        totals["reasoning"] += reasoning
        cost += usage.cost or Decimal(0)
        requests.append(
            {
                "model_name": response.model_name,
                "provider_name": response.provider_name,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "cache_read_tokens": usage.cache_read_tokens,
                "cache_write_tokens": usage.cache_write_tokens,
                "reasoning_tokens": reasoning,
                "details": dict(usage.details),
                "cost": None if usage.cost is None else str(usage.cost),
            }
        )
    last = responses[-1] if responses else None
    return _Usage(
        input_tokens=totals["input"],
        output_tokens=totals["output"],
        cache_read_tokens=totals["cache_read"],
        cache_write_tokens=totals["cache_write"],
        reasoning_tokens=totals["reasoning"],
        cost_usd=cost,
        model_served=last.model_name if last is not None else None,
        provider_served=last.provider_name if last is not None else None,
        raw={"requests": requests},
    )


def mock_embedding(text: str, dimensions: int) -> list[float]:
    """Deterministic vector in [-1, 1]^dimensions, seeded by sha256(text)."""
    seed = int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest(), "big")
    rng = random.Random(seed)
    return [rng.uniform(-1.0, 1.0) for _ in range(dimensions)]


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


class LLMGateway:
    def __init__(
        self,
        *,
        settings: Settings,
        prompts: PromptRegistry,
        recorder: CallRecorder,
        model_factory: ModelFactory,
        search_provider: WebSearchProvider,
    ) -> None:
        self._settings = settings
        self._prompts = prompts
        self._recorder = recorder
        self._model_factory = model_factory
        self._search_provider = search_provider

    async def _check_budget(self, ctx: CallContext) -> None:
        spent = await self._recorder.run_cost(ctx.run_id)
        cap = self._settings.max_cost_per_run_usd
        if spent >= cap:
            raise BudgetExceeded(f"run {ctx.run_id} has spent {spent} USD; the cap is {cap} USD")

    async def _record_agent_attempt(
        self,
        *,
        spec: AgentSpec[Any],
        rendered: RenderedPrompt,
        choice: ModelChoice,
        index: int,
        fallback_from: str | None,
        ctx: CallContext,
        params: Mapping[str, object],
        started: float,
        usage: _Usage,
        provider_fallback: str | None,
        error: Exception | None,
    ) -> None:
        await self._recorder.record(
            CallRecord(
                kind=CallKind.AGENT,
                ctx=ctx,
                provider_requested=choice.provider,
                model_requested=choice.model,
                attempt_index=index,
                status=CallStatus.OK if error is None else CallStatus.ERROR,
                latency_ms=_elapsed_ms(started),
                agent_name=spec.name.value,
                prompt_name=rendered.name,
                prompt_version=rendered.version,
                prompt_sha=rendered.sha256,
                provider_served=usage.provider_served or provider_fallback,
                model_served=usage.model_served,
                fallback_from=fallback_from,
                params=params,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
                cache_write_tokens=usage.cache_write_tokens,
                reasoning_tokens=usage.reasoning_tokens,
                cost_usd=usage.cost_usd,
                usage_raw=usage.raw,
                error_class=None if error is None else type(error).__name__,
                error_message=None if error is None else str(error),
            )
        )

    async def run[OutputT: BaseModel](
        self,
        spec: AgentSpec[OutputT],
        *,
        variables: Mapping[str, object],
        user_prompt: str,
        ctx: CallContext,
    ) -> AgentResult[OutputT]:
        await self._check_budget(ctx)
        rendered = self._prompts.render(spec.prompt_name, variables)
        route = route_for(self._settings, spec.name)
        model_settings: ModelSettings = {"max_tokens": spec.max_output_tokens, "timeout": spec.timeout_seconds}
        params: dict[str, object] = {
            "max_tokens": spec.max_output_tokens,
            "timeout": spec.timeout_seconds,
            "output_retries": spec.output_retries,
            "agent_version": spec.version,
        }
        failures: list[tuple[str, str]] = []
        previous_ref: str | None = None

        for index, choice in enumerate(route):
            if index > 0:
                await self._check_budget(ctx)  # the cap is checked before every model call
            started = time.perf_counter()
            messages: list[ModelMessage] = []
            system: str | None = None
            try:
                with capture_run_messages() as messages:
                    model = self._model_factory.build(choice, spec)
                    system = model.system
                    agent = Agent(
                        model,
                        output_type=spec.output_type,
                        instructions=rendered.text,
                        retries={"output": spec.output_retries},
                    )
                    result = await agent.run(user_prompt, model_settings=model_settings)
            except ADVANCE_ERRORS as exc:
                await self._record_agent_attempt(
                    spec=spec,
                    rendered=rendered,
                    choice=choice,
                    index=index,
                    fallback_from=previous_ref,
                    ctx=ctx,
                    params=params,
                    started=started,
                    usage=_sum_usage(messages),
                    provider_fallback=system,
                    error=exc,
                )
                failures.append((choice.ref(), type(exc).__name__))
                previous_ref = choice.ref()
                continue
            except Exception as exc:
                await self._record_agent_attempt(
                    spec=spec,
                    rendered=rendered,
                    choice=choice,
                    index=index,
                    fallback_from=previous_ref,
                    ctx=ctx,
                    params=params,
                    started=started,
                    usage=_sum_usage(messages),
                    provider_fallback=system,
                    error=exc,
                )
                raise

            usage = _sum_usage(result.all_messages())
            await self._record_agent_attempt(
                spec=spec,
                rendered=rendered,
                choice=choice,
                index=index,
                fallback_from=previous_ref,
                ctx=ctx,
                params=params,
                started=started,
                usage=usage,
                provider_fallback=system,
                error=None,
            )
            return AgentResult(
                output=result.output,
                provider=usage.provider_served or system or choice.provider,
                model=usage.model_served or choice.model,
                attempts=index + 1,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cost_usd=usage.cost_usd,
            )

        raise RouteExhausted(spec.name.value, failures)

    async def search(self, query: SearchQuery, *, ctx: CallContext) -> SearchResult:
        await self._check_budget(ctx)
        provider = self._search_provider
        params = query.model_dump(mode="json")
        started = time.perf_counter()
        try:
            result = await provider.search(query)
        except Exception as exc:
            await self._recorder.record(
                CallRecord(
                    kind=CallKind.SEARCH,
                    ctx=ctx,
                    provider_requested=provider.name,
                    model_requested=provider.name,
                    attempt_index=0,
                    status=CallStatus.ERROR,
                    latency_ms=_elapsed_ms(started),
                    agent_name=AgentName.SEARCH.value,
                    params=params,
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                )
            )
            raise
        await self._recorder.record(
            CallRecord(
                kind=CallKind.SEARCH,
                ctx=ctx,
                provider_requested=provider.name,
                model_requested=provider.name,
                attempt_index=0,
                status=CallStatus.OK,
                latency_ms=result.latency_ms or _elapsed_ms(started),
                agent_name=AgentName.SEARCH.value,
                provider_served=result.provider,
                model_served=result.model,
                params=params,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                search_actions=result.search_actions,
                cost_usd=result.cost_usd,
                usage_raw={
                    "search_actions": result.search_actions,
                    "sources": len(result.sources),
                    "citations": len(result.citations),
                },
            )
        )
        return result

    async def embed(self, texts: Sequence[str], *, ctx: CallContext) -> list[list[float]]:
        if not self._settings.mock_mode:
            raise ProviderNotAvailable("real embeddings are enabled in Phase 2")
        started = time.perf_counter()
        choice = parse_choice(self._settings.embedding_model)
        dimensions = self._settings.embedding_dimensions
        vectors = [mock_embedding(text, dimensions) for text in texts]
        await self._recorder.record(
            CallRecord(
                kind=CallKind.EMBEDDING,
                ctx=ctx,
                provider_requested=choice.provider,
                model_requested=choice.model,
                attempt_index=0,
                status=CallStatus.OK,
                latency_ms=_elapsed_ms(started),
                provider_served=MOCK_EMBEDDING_PROVIDER,
                model_served=MOCK_EMBEDDING_MODEL,
                params={"dimensions": dimensions, "count": len(texts)},
                input_tokens=sum(len(text.split()) for text in texts),
            )
        )
        return vectors


def build_model_factory(settings: Settings) -> ModelFactory:
    if settings.mock_mode:
        # imported here because llm.mock imports AgentSpec/ModelFactory from this module
        from mdcopilot_blog.llm.mock import FixtureRegistry, MockModelFactory

        models.ALLOW_MODEL_REQUESTS = False
        return MockModelFactory(FixtureRegistry.default())
    return UnavailableModelFactory()


def build_gateway(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    prompts: PromptRegistry,
) -> LLMGateway:
    search_provider: WebSearchProvider = FixtureSearchProvider() if settings.mock_mode else UnavailableSearchProvider()
    return LLMGateway(
        settings=settings,
        prompts=prompts,
        recorder=CallRecorder(sessionmaker),
        model_factory=build_model_factory(settings),
        search_provider=search_provider,
    )
