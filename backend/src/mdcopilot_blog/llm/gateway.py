"""LLM gateway: every model and web-search call goes through here.

``run()`` walks the configured route itself (no FallbackModel). Each attempt writes exactly one
``blog_llm_calls`` row. Calls share the same recording and budget enforcement path.
"""

import time
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from mdcopilot_blog.llm.providers import RealModelFactory

import httpx
import httpx2
from pydantic import BaseModel
from pydantic_ai import Agent, ModelResponse, ModelRetry, capture_run_messages
from pydantic_ai.exceptions import ModelAPIError, UnexpectedModelBehavior
from pydantic_ai.messages import ModelMessage
from pydantic_ai.settings import ModelSettings
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog import tracing
from mdcopilot_blog.domain.enums import AgentName, CallKind, CallStatus
from mdcopilot_blog.domain.errors import OutputRejected
from mdcopilot_blog.llm.concurrency import ProviderLimiter, process_limiter
from mdcopilot_blog.llm.pricing import (
    REAL_PROVIDERS,
    SEARCH_FEE_SKU,
    DbPriceBook,
    OverridePrice,
    PriceMissing,
    TokenUsage,
    price_agent_attempt,
    price_search_call,
)
from mdcopilot_blog.llm.recorder import PRICE_VERSION, CallRecord, CallRecorder
from mdcopilot_blog.llm.routes import ModelChoice, model_settings_for, route_for, route_from_entries
from mdcopilot_blog.llm.search.base import SearchQuery, SearchResult, WebSearchProvider
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


@dataclass(frozen=True)
class AgentSpec[OutputT: BaseModel]:
    name: AgentName
    version: str
    prompt_name: str
    output_type: type[OutputT]
    max_output_tokens: int
    output_retries: int = 1
    timeout_seconds: float = 120.0
    reasoning: Literal["minimal", "low", "medium", "high"] | None = None


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


class UnavailableSearchProvider:
    """Fallback used when no configured real web-search provider can be built."""

    name = "unavailable"

    async def search(self, query: SearchQuery) -> SearchResult:
        raise ProviderNotAvailable("no real web-search provider is configured")


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
    any_cost: bool
    raw: dict[str, object]


def _sum_usage(messages: Sequence[ModelMessage]) -> _Usage:
    responses = [m for m in messages if isinstance(m, ModelResponse)]
    requests: list[dict[str, object]] = []
    totals = {"input": 0, "output": 0, "cache_read": 0, "cache_write": 0, "reasoning": 0}
    cost = Decimal(0)
    any_cost = False
    for response in responses:
        usage = response.usage
        reasoning = int(getattr(usage, "output_reasoning_tokens", 0) or 0)
        totals["input"] += usage.input_tokens
        totals["output"] += usage.output_tokens
        totals["cache_read"] += usage.cache_read_tokens
        totals["cache_write"] += usage.cache_write_tokens
        totals["reasoning"] += reasoning
        if usage.cost is not None:
            any_cost = True
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
        any_cost=any_cost,
        raw={"requests": requests},
    )


def _detail_int(details: Mapping[str, object], key: str) -> int:
    value = details.get(key)
    return value if isinstance(value, int) else 0


def _elapsed_ms(started: float) -> int:
    return int((time.perf_counter() - started) * 1000)


def _attach_output_check[OutputT: BaseModel](agent: Agent[None, OutputT], check: Callable[[OutputT], None]) -> None:
    @agent.output_validator
    def _validate(output: OutputT) -> OutputT:
        try:
            check(output)
        except OutputRejected as exc:
            raise ModelRetry(exc.args[0]) from exc
        return output


class LLMGateway:
    def __init__(
        self,
        *,
        settings: Settings,
        prompts: PromptRegistry,
        recorder: CallRecorder,
        model_factory: "RealModelFactory",
        search_provider: WebSearchProvider,
        limiter: ProviderLimiter,
        price_book: DbPriceBook,
    ) -> None:
        self._settings = settings
        self._prompts = prompts
        self._recorder = recorder
        self._model_factory = model_factory
        self._search_provider = search_provider
        self._limiter = limiter
        self._price_book = price_book

    async def _check_budget(self, ctx: CallContext) -> None:
        if ctx.run_id is None and ctx.attempt_id is None:
            return  # calls with neither id are uncapped
        spent = await self._recorder.budget_spent(ctx)
        cap = self._settings.max_cost_per_run_usd
        if spent >= cap:
            raise BudgetExceeded(
                f"run {ctx.run_id} (attempt {ctx.attempt_id}) has spent {spent} USD; the cap is {cap} USD"
            )

    async def _record_agent_attempt(
        self,
        *,
        gen: Any,
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
        cost_usd: Decimal | None = None,
        price_version: str | None = None,
        raw_extra: dict[str, object] | None = None,
    ) -> None:
        """Write the attempt's ledger row, then fill its generation from that row (gen is None when tracing is off)."""
        rec = CallRecord(
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
            cost_usd=usage.cost_usd if cost_usd is None else cost_usd,
            usage_raw={**usage.raw, **(raw_extra or {})},
            price_version=PRICE_VERSION if price_version is None else price_version,
            error_class=None if error is None else type(error).__name__,
            error_message=None if error is None else str(error),
        )
        row_id = await self._recorder.record(rec)  # the row id exists only after the insert (recorder.py:101)
        if gen is not None:
            tracing.update_generation(gen, rec, ledger_row_id=row_id)

    async def _price_attempt(
        self, choice: ModelChoice, system: str | None, usage: _Usage, at: datetime
    ) -> tuple[Decimal, str, dict[str, object]]:
        """Price one attempt using the configured price book."""
        priced = await price_agent_attempt(
            self._price_book,
            provider_requested=choice.provider,
            model_requested=choice.model,
            provider_served=usage.provider_served or system,
            model_served=usage.model_served,
            usage=TokenUsage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
            ),
            sdk_cost=usage.cost_usd if usage.any_cost else None,
            at=at,
        )
        return priced.cost_usd, priced.price_version, {"pricing": priced.source}

    async def run[OutputT: BaseModel](
        self,
        spec: AgentSpec[OutputT],
        *,
        variables: Mapping[str, object],
        user_prompt: str,
        ctx: CallContext,
        route_override: Sequence[str] | None = None,
        output_check: Callable[[OutputT], None] | None = None,
    ) -> AgentResult[OutputT]:
        await self._check_budget(ctx)
        rendered = self._prompts.render(spec.prompt_name, variables)
        if route_override is None:
            route = route_for(self._settings, spec.name)
        else:
            route = route_from_entries(self._settings, spec.name, route_override)
        params: dict[str, object] = {
            "max_tokens": spec.max_output_tokens,
            "timeout": spec.timeout_seconds,
            "output_retries": spec.output_retries,
            "agent_version": spec.version,
        }
        failures: list[tuple[str, str]] = []
        previous_ref: str | None = None
        # Allowlisted model parameters for the generation; params also holds timeout and agent_version.
        model_params: dict[str, object] = {"max_tokens": spec.max_output_tokens}
        if spec.reasoning is not None:
            model_params["reasoning_effort"] = spec.reasoning

        for index, choice in enumerate(route):
            if index > 0:
                await self._check_budget(ctx)  # the cap is checked before every model call
            model_settings: ModelSettings = model_settings_for(
                choice,
                max_tokens=spec.max_output_tokens,
                timeout_seconds=spec.timeout_seconds,
                reasoning=spec.reasoning,
            )

            # One generation per route attempt, i.e. per blog_llm_calls row; gen is None when tracing is off.
            with tracing.generation(
                f"llm.{choice.provider}.complete",
                model=choice.model,
                model_parameters=model_params,
            ) as gen:
                if gen is not None and tracing.capture_full():
                    sent = [{"role": "system", "content": rendered.text}, {"role": "user", "content": user_prompt}]
                    gen.update(input=tracing.content(sent))
                at = datetime.now(UTC)
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
                        if output_check is not None:
                            _attach_output_check(agent, output_check)
                        async with self._limiter.slot(choice.provider):
                            result = await agent.run(user_prompt, model_settings=model_settings)
                except ADVANCE_ERRORS as exc:
                    failed_usage = _sum_usage(messages)
                    cost_usd, price_version, raw_extra = await self._price_attempt(choice, system, failed_usage, at)
                    await self._record_agent_attempt(
                        gen=gen,
                        spec=spec,
                        rendered=rendered,
                        choice=choice,
                        index=index,
                        fallback_from=previous_ref,
                        ctx=ctx,
                        params=params,
                        started=started,
                        usage=failed_usage,
                        provider_fallback=system,
                        error=exc,
                        cost_usd=cost_usd,
                        price_version=price_version,
                        raw_extra=raw_extra,
                    )
                    failures.append((choice.ref(), type(exc).__name__))
                    previous_ref = choice.ref()
                    continue
                except Exception as exc:
                    failed_usage = _sum_usage(messages)
                    cost_usd, price_version, raw_extra = await self._price_attempt(choice, system, failed_usage, at)
                    await self._record_agent_attempt(
                        gen=gen,
                        spec=spec,
                        rendered=rendered,
                        choice=choice,
                        index=index,
                        fallback_from=previous_ref,
                        ctx=ctx,
                        params=params,
                        started=started,
                        usage=failed_usage,
                        provider_fallback=system,
                        error=exc,
                        cost_usd=cost_usd,
                        price_version=price_version,
                        raw_extra=raw_extra,
                    )
                    raise

                usage = _sum_usage(result.all_messages())
                cost_usd, price_version, raw_extra = await self._price_attempt(choice, system, usage, at)
                await self._record_agent_attempt(
                    gen=gen,
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
                    cost_usd=cost_usd,
                    price_version=price_version,
                    raw_extra=raw_extra,
                )
                if gen is not None and tracing.capture_full():
                    gen.update(output=tracing.content(result.output.model_dump(mode="json")))
                return AgentResult(
                    output=result.output,
                    provider=usage.provider_served or system or choice.provider,
                    model=usage.model_served or choice.model,
                    attempts=index + 1,
                    input_tokens=usage.input_tokens,
                    output_tokens=usage.output_tokens,
                    cost_usd=cost_usd,
                )

        raise RouteExhausted(spec.name.value, failures)

    async def search(self, query: SearchQuery, *, ctx: CallContext) -> SearchResult:
        await self._check_budget(ctx)
        provider = self._search_provider
        params = query.model_dump(mode="json")
        started = time.perf_counter()

        model_requested = getattr(provider, "model", None)
        if not isinstance(model_requested, str):
            model_requested = provider.name
        provider_served_key = provider.name
        is_real = provider_served_key in REAL_PROVIDERS
        at: datetime | None = None
        fee: OverridePrice | None = None
        if is_real:
            at = datetime.now(UTC)
            fee = await self._price_book.override_for(provider_served_key, SEARCH_FEE_SKU, at=at)
            if fee is None or fee.per_1k_calls is None:
                raise PriceMissing(provider_served_key, SEARCH_FEE_SKU)

        # One generation per search attempt, i.e. per blog_llm_calls row; gen is None when tracing is off.
        with tracing.generation(
            f"llm.{provider.name}.responses",
            model=model_requested,
            metadata={"purpose": "web_search", "mode": query.mode},
        ) as gen:
            if gen is not None and tracing.capture_full():
                gen.update(input=tracing.content(query.text))
            try:
                async with self._limiter.slot(provider.name):
                    result = await provider.search(query)
            except Exception as exc:
                rec = CallRecord(
                    kind=CallKind.SEARCH,
                    ctx=ctx,
                    provider_requested=provider.name,
                    model_requested=model_requested,
                    attempt_index=0,
                    status=CallStatus.ERROR,
                    latency_ms=_elapsed_ms(started),
                    agent_name=AgentName.SEARCH.value,
                    params=params,
                    error_class=type(exc).__name__,
                    error_message=str(exc),
                )
                row_id = await self._recorder.record(rec)
                if gen is not None:
                    tracing.update_generation(gen, rec, ledger_row_id=row_id)
                raise

            details = getattr(result, "usage_details", None)
            details = dict(details) if isinstance(details, Mapping) else {}
            cache_read_tokens = _detail_int(details, "cache_read_tokens")
            reasoning_tokens = _detail_int(details, "reasoning_tokens")
            cost_usd = result.cost_usd
            price_version: str = PRICE_VERSION
            if is_real and fee is not None and at is not None:
                priced = await price_search_call(
                    self._price_book,
                    provider_requested=provider.name,
                    model_requested=model_requested,
                    provider_served=result.provider,
                    model_served=result.model,
                    usage=TokenUsage(result.input_tokens, result.output_tokens, cache_read_tokens),
                    search_actions=result.search_actions,
                    fee=fee,
                    at=at,
                )
                cost_usd, price_version = priced.cost_usd, priced.price_version
                details["pricing"] = priced.source
            usage_raw: dict[str, object] = dict(details)
            usage_raw["search_actions"] = result.search_actions
            usage_raw["sources"] = len(result.sources)
            usage_raw["citations"] = len(result.citations)
            rec = CallRecord(
                kind=CallKind.SEARCH,
                ctx=ctx,
                provider_requested=provider.name,
                model_requested=model_requested,
                attempt_index=0,
                status=CallStatus.OK,
                latency_ms=result.latency_ms or _elapsed_ms(started),
                agent_name=AgentName.SEARCH.value,
                provider_served=result.provider,
                model_served=result.model,
                params=params,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                cache_read_tokens=cache_read_tokens,
                reasoning_tokens=reasoning_tokens,
                search_actions=result.search_actions,
                cost_usd=cost_usd,
                price_version=price_version,
                usage_raw=usage_raw,
            )
            row_id = await self._recorder.record(rec)
            if gen is not None and tracing.capture_full():
                gen.update(output=tracing.content(result.answer_text))
            if gen is not None:
                tracing.update_generation(gen, rec, ledger_row_id=row_id)
        return result


def build_gateway(
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    prompts: PromptRegistry,
) -> LLMGateway:
    search_provider: WebSearchProvider
    try:
        from mdcopilot_blog.llm.search.openai import OpenAIWebSearchProvider

        search_provider = OpenAIWebSearchProvider(settings)
    except ProviderNotAvailable:
        search_provider = UnavailableSearchProvider()
    from mdcopilot_blog.llm.pricing import DbPriceBook, ensure_price_updates
    from mdcopilot_blog.llm.providers import RealModelFactory

    ensure_price_updates(settings)
    return LLMGateway(
        settings=settings,
        prompts=prompts,
        recorder=CallRecorder(sessionmaker),
        model_factory=RealModelFactory(settings),
        search_provider=search_provider,
        limiter=process_limiter(settings.provider_concurrency),
        price_book=DbPriceBook(sessionmaker),
    )
