"""seed_defaults: inserts the spec defaults once and never duplicates them."""

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import BlogSetting, BrandProfile, ContentPillar
from mdcopilot_blog.db.seed import SeedReport, load_seed_file, seed_defaults

PILLAR_A_TOPICS = [
    "specialist shortages",
    "wait times",
    "regional disparities",
    "referral bottlenecks",
    "specialist access",
    "scaling specialist expertise",
    "underserved populations",
]


async def _count(session: AsyncSession, model: type[BlogSetting | BrandProfile | ContentPillar]) -> int:
    value = await session.scalar(select(func.count()).select_from(model))
    return int(value or 0)


async def test_seed_defaults_is_idempotent(db_session: AsyncSession) -> None:
    first = await seed_defaults(db_session)
    second = await seed_defaults(db_session)

    assert first == SeedReport(settings_created=True, brand_created=True, pillars_created=6)
    assert second == SeedReport(settings_created=False, brand_created=False, pillars_created=0)
    assert await _count(db_session, BlogSetting) == 1
    assert await _count(db_session, BrandProfile) == 1
    assert await _count(db_session, ContentPillar) == 6


async def test_seeded_versions_are_active_version_one(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    setting = await db_session.scalar(select(BlogSetting))
    brand = await db_session.scalar(select(BrandProfile))
    assert setting is not None
    assert brand is not None
    assert (setting.version, setting.is_active) == (1, True)
    assert (brand.version, brand.is_active) == (1, True)
    assert setting.values["schedule"] == {"time": "07:00", "timezone": "Asia/Kolkata"}
    assert setting.values["gate_override_policy"] == "admin_with_reason"
    assert abs(sum(setting.values["score_weights"].values()) - 1.0) < 1e-9
    assert brand.profile["narrative"] == "an amplifier of specialist leverage, not a replacement for physicians"
    assert brand.profile["ai_disclosure"] == (
        "This article was researched and drafted with AI assistance and reviewed by the MDCopilot team."
    )
    assert "AI is transforming healthcare" in brand.profile["prohibited_language"]
    assert brand.profile["target_word_count"] == {"min": 850, "max": 1150}
    assert brand.profile["website"] == "https://www.mdcopilot.health"


async def test_pillars_follow_spec_rotation(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    pillars = (await db_session.scalars(select(ContentPillar).order_by(ContentPillar.sort_order))).all()

    assert [(p.key, p.weekdays) for p in pillars] == [
        ("A", [0]),
        ("B", [1]),
        ("C", [2]),
        ("D", [3]),
        ("E", [4]),
        ("NARRATIVE", [5, 6]),
    ]
    assert [p.name for p in pillars] == [
        "Specialist Scarcity & Access",
        "Cognitive Architecture & Physician Reasoning",
        "Burnout & Administrative Overload",
        "The Agentic Shift",
        "Governance & Clinical Autonomy",
        "Narrative Edition",
    ]
    assert pillars[0].topics == PILLAR_A_TOPICS
    assert "deterministic guardrails" in pillars[4].topics
    assert "Clinic of 2030" in pillars[5].topics
    assert all(p.is_active and p.description for p in pillars)


async def test_seed_restores_only_missing_pillars(db_session: AsyncSession) -> None:
    await seed_defaults(db_session)
    edited = await db_session.scalar(select(ContentPillar).where(ContentPillar.key == "A"))
    assert edited is not None
    edited.name = "Edited by an admin"
    await db_session.execute(delete(ContentPillar).where(ContentPillar.key == "C"))
    await db_session.flush()

    report = await seed_defaults(db_session)

    assert report == SeedReport(settings_created=False, brand_created=False, pillars_created=1)
    names = dict((await db_session.execute(select(ContentPillar.key, ContentPillar.name))).tuples().all())
    assert names["A"] == "Edited by an admin"
    assert names["C"] == "Burnout & Administrative Overload"


def test_seed_files_are_package_data() -> None:
    assert len(load_seed_file("pillars.yaml")["pillars"]) == 6
    assert load_seed_file("brand_profile.yaml")["name"] == "MDCopilot"
    assert set(load_seed_file("settings.yaml")) == {
        "schedule",
        "novelty_threshold",
        "score_weights",
        "gate_override_policy",
    }
