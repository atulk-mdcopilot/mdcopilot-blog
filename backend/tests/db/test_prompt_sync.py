"""PromptRegistry.sync_to_db against the disposable test database."""

import hashlib
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import PromptVersion
from mdcopilot_blog.prompts.registry import PromptRegistry, PromptRegistryError, default_prompt_root

PROMPT_TEXT = (
    "---\n"
    "name: sync_agent/greet\n"
    "version: 1\n"
    "agent: sync_agent\n"
    "output: GreetOutput\n"
    "variables:\n"
    "  - who\n"
    "---\n"
    "Greet {{ who }}.\n"
)


def make_registry(root: Path) -> PromptRegistry:
    path = root / "sync_agent" / "greet.v1.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(PROMPT_TEXT, encoding="utf-8")
    return PromptRegistry.from_directory(root)


async def test_sync_inserts_missing_rows_once(db_session: AsyncSession, tmp_path: Path) -> None:
    registry = make_registry(tmp_path)

    assert await registry.sync_to_db(db_session) == 1
    assert await registry.sync_to_db(db_session) == 0

    rows = (await db_session.scalars(select(PromptVersion).where(PromptVersion.name == "sync_agent/greet"))).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.version == 1
    assert row.agent == "sync_agent"
    assert row.sha256 == hashlib.sha256(PROMPT_TEXT.encode("utf-8")).hexdigest()
    assert row.body == "Greet {{ who }}.\n"
    assert row.front_matter == {
        "name": "sync_agent/greet",
        "version": 1,
        "agent": "sync_agent",
        "output": "GreetOutput",
        "variables": ["who"],
    }


async def test_sync_refuses_changed_text_without_version_bump(db_session: AsyncSession, tmp_path: Path) -> None:
    registry = make_registry(tmp_path)
    db_session.add(
        PromptVersion(
            name="sync_agent/greet",
            version=1,
            agent="sync_agent",
            sha256="0" * 64,
            body="an older text",
            front_matter={},
        )
    )
    await db_session.flush()

    with pytest.raises(PromptRegistryError, match="prompt sync_agent/greet v1 changed without a version bump"):
        await registry.sync_to_db(db_session)


async def test_sync_registers_the_shipped_prompts(db_session: AsyncSession) -> None:
    registry = PromptRegistry.from_directory(default_prompt_root())
    await registry.sync_to_db(db_session)
    assert await registry.sync_to_db(db_session) == 0
    row = await db_session.scalar(
        select(PromptVersion).where(PromptVersion.name == "hello/echo", PromptVersion.version == 1)
    )
    assert row is not None
    assert row.sha256 == registry.get("hello/echo", version=1).sha256
