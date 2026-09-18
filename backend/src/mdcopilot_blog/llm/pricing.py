"""Pricing: genai-prices plus ``blog_price_overrides``; quantized to 6 decimals."""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from typing import Final, Literal

from genai_prices import Usage, calc_price
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import PriceOverride
from mdcopilot_blog.llm.recorder import PRICE_VERSION
from mdcopilot_blog.settings import Settings

GENAI_PRICES_VERSION: Final = PRICE_VERSION
REAL_PROVIDERS: Final = frozenset({"openai", "google", "anthropic"})
SEARCH_FEE_SKU: Final = "web_search_call"
_MILLION: Final = Decimal(1_000_000)

PricingSource = Literal["genai-prices", "override", "unpriced"]


@dataclass(frozen=True)
class OverridePrice:
    provider: str
    sku: str
    input_per_mtok: Decimal | None
    output_per_mtok: Decimal | None
    cache_read_per_mtok: Decimal | None
    per_1k_calls: Decimal | None
    effective_from: datetime
    price_version: str


@dataclass(frozen=True)
class TokenUsage:
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int = 0


@dataclass(frozen=True)
class PricedCall:
    cost_usd: Decimal
    price_version: str
    source: PricingSource
    override_versions: tuple[str, ...]


class PriceMissing(RuntimeError):
    def __init__(self, provider: str, sku: str) -> None:
        super().__init__(f"no effective price override for ({provider}, {sku})")
        self.provider = provider
        self.sku = sku

    def __reduce__(self) -> tuple[object, ...]:
        return (PriceMissing, (self.provider, self.sku))


def _check_at(at: datetime) -> None:
    if at.tzinfo is None:
        raise ValueError("at must be timezone-aware")


class DbPriceBook:
    """Reads ``blog_price_overrides`` per call (no cache)."""

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def override_for(self, provider: str, sku: str, *, at: datetime) -> OverridePrice | None:
        _check_at(at)
        async with self._sessionmaker() as session:
            row = (
                (
                    await session.execute(
                        select(PriceOverride)
                        .where(
                            PriceOverride.provider == provider,
                            PriceOverride.sku == sku,
                            PriceOverride.effective_from <= at,
                        )
                        .order_by(PriceOverride.effective_from.desc())
                        .limit(1)
                    )
                )
                .scalars()
                .first()
            )
            if row is None:
                return None
            return OverridePrice(
                provider=row.provider,
                sku=row.sku,
                input_per_mtok=row.input_per_mtok,
                output_per_mtok=row.output_per_mtok,
                cache_read_per_mtok=row.cache_read_per_mtok,
                per_1k_calls=row.per_1k_calls,
                effective_from=row.effective_from,
                price_version=row.price_version,
            )


def quantize_usd(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.000001"), rounding=ROUND_HALF_UP)


def override_token_cost(price: OverridePrice, usage: TokenUsage) -> Decimal | None:
    """The override's token cost, or None when the override does not price every used component."""
    cache = min(usage.cache_read_tokens, usage.input_tokens)
    uncached = usage.input_tokens - cache
    cache_price = price.cache_read_per_mtok if price.cache_read_per_mtok is not None else price.input_per_mtok
    if price.input_per_mtok is None and price.output_per_mtok is None:
        return None
    if uncached > 0 and price.input_per_mtok is None:
        return None
    if cache > 0 and cache_price is None:
        return None
    if usage.output_tokens > 0 and price.output_per_mtok is None:
        return None
    input_cost = Decimal(uncached) * (price.input_per_mtok or Decimal(0))
    cache_cost = Decimal(cache) * (cache_price or Decimal(0))
    output_cost = Decimal(usage.output_tokens) * (price.output_per_mtok or Decimal(0))
    return quantize_usd((input_cost + cache_cost + output_cost) / _MILLION)


def search_fee(price: OverridePrice, search_actions: int) -> Decimal:
    if search_actions < 0:
        raise ValueError("search_actions must be >= 0")
    if price.per_1k_calls is None:
        raise PriceMissing(price.provider, price.sku)
    return quantize_usd(Decimal(search_actions) * price.per_1k_calls / Decimal(1000))


def genai_token_cost(provider: str, model: str, usage: TokenUsage, *, at: datetime) -> Decimal | None:
    if provider not in REAL_PROVIDERS:
        return None
    try:
        priced = calc_price(
            Usage(
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
            ),
            model,
            provider_id=provider,
            genai_request_timestamp=at,
        )
    except LookupError:
        return None
    return quantize_usd(priced.total_price)


def price_version_for(override_versions: Sequence[str]) -> str:
    if not override_versions:
        return GENAI_PRICES_VERSION
    joined = GENAI_PRICES_VERSION + ";" + ";".join(override_versions)
    if len(joined) > 64:
        raise ValueError("price_version exceeds 64 characters")
    return joined


async def price_agent_attempt(
    book: DbPriceBook,
    *,
    provider_requested: str,
    model_requested: str,
    provider_served: str | None,
    model_served: str | None,
    usage: TokenUsage,
    sdk_cost: Decimal | None,
    at: datetime,
) -> PricedCall:
    requested = await book.override_for(provider_requested, model_requested, at=at)
    if requested is not None:
        cost = override_token_cost(requested, usage)
        if cost is not None:
            return PricedCall(
                cost, price_version_for([requested.price_version]), "override", (requested.price_version,)
            )
    if (
        provider_served is not None
        and model_served is not None
        and (provider_served, model_served)
        != (
            provider_requested,
            model_requested,
        )
    ):
        served = await book.override_for(provider_served, model_served, at=at)
        if served is not None:
            cost = override_token_cost(served, usage)
            if cost is not None:
                return PricedCall(cost, price_version_for([served.price_version]), "override", (served.price_version,))
    if sdk_cost is not None:
        return PricedCall(quantize_usd(sdk_cost), GENAI_PRICES_VERSION, "genai-prices", ())
    return PricedCall(Decimal("0.000000"), GENAI_PRICES_VERSION, "unpriced", ())


async def price_search_call(
    book: DbPriceBook,
    *,
    provider_requested: str,
    model_requested: str,
    provider_served: str,
    model_served: str,
    usage: TokenUsage,
    search_actions: int,
    fee: OverridePrice,
    at: datetime,
) -> PricedCall:
    """Token part by the override order (requested, then served), else genai-prices; plus the fee."""
    override_version: str | None = None
    source: PricingSource = "unpriced"
    token_cost = Decimal(0)

    requested = await book.override_for(provider_requested, model_requested, at=at)
    requested_cost = override_token_cost(requested, usage) if requested is not None else None
    if requested_cost is not None and requested is not None:
        token_cost, source, override_version = requested_cost, "override", requested.price_version
    else:
        token_cost, source = await _genai_or_zero(
            book, provider_served, model_served, provider_requested, model_requested, usage, at
        )

    total = quantize_usd(token_cost + search_fee(fee, search_actions))
    versions = [version for version in (override_version, fee.price_version) if version is not None]
    return PricedCall(total, price_version_for(versions), source, tuple(versions))


async def _genai_or_zero(
    book: DbPriceBook,
    provider_served: str,
    model_served: str,
    provider_requested: str,
    model_requested: str,
    usage: TokenUsage,
    at: datetime,
) -> tuple[Decimal, PricingSource]:
    cost = genai_token_cost(provider_served, model_served, usage, at=at)
    if cost is None:
        cost = genai_token_cost(provider_requested, model_requested, usage, at=at)
    if cost is None:
        return Decimal(0), "unpriced"
    return cost, "genai-prices"


async def price_embedding_call(
    book: DbPriceBook,
    *,
    provider: str,
    model: str,
    input_tokens: int,
    at: datetime,
) -> PricedCall:
    override = await book.override_for(provider, model, at=at)
    if override is not None:
        cost = override_token_cost(override, TokenUsage(input_tokens, 0))
        if cost is not None:
            return PricedCall(cost, price_version_for([override.price_version]), "override", (override.price_version,))
    cost = genai_token_cost(provider, model, TokenUsage(input_tokens, 0), at=at)
    if cost is not None:
        return PricedCall(cost, GENAI_PRICES_VERSION, "genai-prices", ())
    return PricedCall(Decimal("0.000000"), GENAI_PRICES_VERSION, "unpriced", ())


_PRICE_UPDATER: object | None = None


def ensure_price_updates(settings: Settings) -> bool:
    global _PRICE_UPDATER
    if not settings.price_auto_update or _PRICE_UPDATER is not None:
        return False
    from pydantic_ai import prices as pai_prices

    _PRICE_UPDATER = pai_prices.update_in_background()
    return True
