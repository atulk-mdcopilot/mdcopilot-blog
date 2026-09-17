"""Idempotent default data: settings v1, brand profile v1 and the six content pillars.

The YAML files in ``db/seed_data/`` are package data, read with ``importlib.resources``.
``seed_defaults`` only flushes; the caller commits.
"""

from dataclasses import dataclass
from importlib import resources
from typing import Any

import yaml
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogSetting, BrandProfile, ContentPillar

SEED_VERSION = 1


@dataclass(frozen=True)
class SeedReport:
    settings_created: bool
    brand_created: bool
    pillars_created: int


def load_seed_file(name: str) -> dict[str, Any]:
    raw = (resources.files("mdcopilot_blog.db") / "seed_data" / name).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    if not isinstance(data, dict):
        msg = f"seed file {name} must contain a mapping"
        raise TypeError(msg)
    return data


async def seed_defaults(session: AsyncSession) -> SeedReport:
    """Insert whatever is missing. Existing rows (including edited ones) are never touched."""
    settings_created = False
    if await session.scalar(select(BlogSetting.id).limit(1)) is None:
        session.add(BlogSetting(version=SEED_VERSION, values=load_seed_file("settings.yaml"), is_active=True))
        settings_created = True

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

    await session.flush()
    return SeedReport(settings_created=settings_created, brand_created=brand_created, pillars_created=pillars_created)
