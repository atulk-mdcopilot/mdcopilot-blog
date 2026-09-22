"""Idempotent default data: brand profile v1, the six content pillars, source domains and price overrides.

The YAML files in ``db/seed_data/`` are package data, read with ``importlib.resources``.
``seed_defaults`` only flushes; the caller commits. Existing rows (including edited ones)
are never updated; catalogue rows are inserted by natural key only.
"""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from importlib import resources
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BrandProfile, ContentPillar, PriceOverride, SourceDomain
from mdcopilot_blog.domain.contracts import SourceType
from mdcopilot_blog.ids import uuid7

SEED_VERSION = 1

_HEADER_PROFILES = ("default", "browser_like")
_FETCH_POLICIES = ("fetch", "metadata_only", "never")
_SOURCE_TYPES = tuple(kind.value for kind in SourceType)


@dataclass(frozen=True)
class SeedReport:
    brand_created: bool
    pillars_created: int
    domains_created: int = 0
    price_overrides_created: int = 0


def load_seed_file(name: str) -> dict[str, Any]:
    raw = (resources.files("mdcopilot_blog.db") / "seed_data" / name).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"seed file {name} must contain a mapping"
        raise TypeError(msg)
    return data


def _required(item: dict[str, Any], file: str, index: int, key: str) -> Any:
    if key not in item:
        raise ValueError(f"{file} item {index}: missing key '{key}'")
    return item[key]


def _allowed(value: Any, file: str, index: int, field: str, allowed: tuple[str, ...]) -> str:
    text = str(value)
    if text not in allowed:
        raise ValueError(f"{file} item {index}: {field} {value!r} is not allowed")
    return text


def _tier(value: Any, file: str, index: int) -> int:
    tier = int(value)
    if tier not in (1, 2, 3):
        raise ValueError(f"{file} item {index}: tier {value!r} is not allowed")
    return tier


def _domain(file: str, index: int, item: dict[str, Any]) -> SourceDomain:
    domain = str(_required(item, file, index, "domain"))
    if domain != domain.lower():
        raise ValueError(f"{file} item {index}: domain must be lowercase")
    return SourceDomain(
        domain=domain,
        tier=_tier(_required(item, file, index, "tier"), file, index),
        source_type=_allowed(_required(item, file, index, "source_type"), file, index, "source_type", _SOURCE_TYPES),
        publisher=item.get("publisher"),
        header_profile=_allowed(item.get("header_profile", "default"), file, index, "header_profile", _HEADER_PROFILES),
        fetch_policy=_allowed(item.get("fetch_policy", "fetch"), file, index, "fetch_policy", _FETCH_POLICIES),
        verification_allowlisted=bool(item.get("verification_allowlisted", False)),
        notes=item.get("notes"),
    )


def _override_effective_from(value: Any, file: str, index: int) -> datetime:
    if isinstance(value, datetime):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, date):
        return datetime(value.year, value.month, value.day, tzinfo=UTC)
    if isinstance(value, str):
        parsed = date.fromisoformat(value)
        return datetime(parsed.year, parsed.month, parsed.day, tzinfo=UTC)
    raise ValueError(f"{file} item {index}: effective_from {value!r} is not a date")


def _price(item: dict[str, Any], key: str) -> Decimal | None:
    value = item.get(key)
    return None if value is None else Decimal(str(value))


def _price_override(file: str, index: int, item: dict[str, Any]) -> PriceOverride:
    if item.get("input_per_mtok") is None and item.get("output_per_mtok") is None and item.get("per_1k_calls") is None:
        raise ValueError(
            f"{file} item {index}: at least one of input_per_mtok, output_per_mtok, per_1k_calls is required"
        )
    override_id = uuid7()
    return PriceOverride(
        id=override_id,
        provider=str(_required(item, file, index, "provider")),
        sku=str(_required(item, file, index, "sku")),
        input_per_mtok=_price(item, "input_per_mtok"),
        output_per_mtok=_price(item, "output_per_mtok"),
        cache_read_per_mtok=_price(item, "cache_read_per_mtok"),
        per_1k_calls=_price(item, "per_1k_calls"),
        effective_from=_override_effective_from(_required(item, file, index, "effective_from"), file, index),
        price_version="ovr:" + override_id.hex[-12:],
        note=item.get("note"),
    )


async def seed_defaults(session: AsyncSession) -> SeedReport:
    """Insert whatever is missing. Existing rows (including edited ones) are never touched."""
    brand_created = False
    if await session.scalar(select(BrandProfile.id).limit(1)) is None:
        session.add(BrandProfile(version=SEED_VERSION, profile=load_seed_file("brand_profile.yaml"), is_active=True))
        brand_created = True

    existing_keys = set((await session.scalars(select(ContentPillar.key))).all())
    pillars_created = 0
    for position, item in enumerate(load_seed_file("pillars.yaml")["pillars"]):
        key = str(item["key"])
        if key in existing_keys:
            continue
        session.add(
            ContentPillar(
                key=key,
                name=str(item["name"]),
                description=str(item["description"]),
                topics=[str(topic) for topic in item["topics"]],
                weekdays=[int(day) for day in item["weekdays"]],
                is_active=True,
                sort_order=position,
            )
        )
        pillars_created += 1

    domains_created = 0
    existing_domains = set((await session.scalars(select(SourceDomain.domain))).all())
    for index, item in enumerate(load_seed_file("domains.yaml")["domains"]):
        domain = _domain("domains.yaml", index, item)
        if domain.domain in existing_domains:
            continue
        session.add(domain)
        domains_created += 1

    price_overrides_created = 0
    existing_overrides = set(
        (await session.execute(select(PriceOverride.provider, PriceOverride.sku, PriceOverride.effective_from)))
        .tuples()
        .all()
    )
    for index, item in enumerate(load_seed_file("price_overrides.yaml")["price_overrides"]):
        override = _price_override("price_overrides.yaml", index, item)
        if (override.provider, override.sku, override.effective_from) in existing_overrides:
            continue
        session.add(override)
        price_overrides_created += 1

    await session.flush()
    return SeedReport(
        brand_created=brand_created,
        pillars_created=pillars_created,
        domains_created=domains_created,
        price_overrides_created=price_overrides_created,
    )
