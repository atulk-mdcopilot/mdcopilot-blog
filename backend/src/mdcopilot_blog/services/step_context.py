"""Shared configuration, providers and database access for each workflow step."""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig
from mdcopilot_blog.llm.gateway import CallContext, LLMGateway
from mdcopilot_blog.prompts.registry import PromptRegistry
from mdcopilot_blog.services.config import load_brand_profile, load_effective_config
from mdcopilot_blog.settings import Settings


@dataclass(frozen=True)
class StepContext:
    settings: Settings
    config: EffectiveConfig
    brand: BrandProfileValues
    sessionmaker: async_sessionmaker[AsyncSession]
    gateway: LLMGateway
    prompts: PromptRegistry
    call: CallContext

    def with_ids(
        self, *, article_id: uuid.UUID | None = None, topic_candidate_id: uuid.UUID | None = None
    ) -> "StepContext":
        call = self.call
        return dataclasses.replace(
            self,
            call=dataclasses.replace(
                call,
                article_id=article_id if article_id is not None else call.article_id,
                topic_candidate_id=topic_candidate_id if topic_candidate_id is not None else call.topic_candidate_id,
            ),
        )

    def now(self) -> datetime:
        return datetime.now(UTC)


async def build_step_context(
    *,
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    gateway: LLMGateway,
    prompts: PromptRegistry,
    call: CallContext,
) -> StepContext:
    """Load the effective config and brand profile from committed rows, never from YAML."""
    async with sessionmaker() as db:
        config = await load_effective_config(db, settings, run_id=call.run_id)
        brand = await load_brand_profile(db)
    return StepContext(
        settings=settings,
        config=config,
        brand=brand,
        sessionmaker=sessionmaker,
        gateway=gateway,
        prompts=prompts,
        call=call,
    )
