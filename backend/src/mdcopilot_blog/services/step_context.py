"""Shared configuration, providers and database access for each workflow step."""

import dataclasses
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from mdcopilot_blog.db.models import BlogRun
from mdcopilot_blog.domain.config import BrandProfileValues, EffectiveConfig
from mdcopilot_blog.ids import new_trace_id
from mdcopilot_blog.llm.gateway import CallContext, LLMGateway
from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root
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


async def build_api_step_context(
    *,
    settings: Settings,
    sessionmaker: async_sessionmaker[AsyncSession],
    run_id: uuid.UUID | None,
    article_id: uuid.UUID | None,
) -> StepContext:
    """The API's step context: one run means one trace id."""
    prompts = PromptRegistry.from_directory(default_prompt_root())
    from mdcopilot_blog.llm.gateway import build_gateway

    gateway = build_gateway(settings, sessionmaker, prompts)
    if run_id is None:
        trace_id = new_trace_id()
    else:
        async with sessionmaker() as db:
            run = await db.get(BlogRun, run_id)
            if run is None:
                raise LookupError(f"run {run_id} not found")
            trace_id = run.trace_id
    call = CallContext(trace_id=trace_id, run_id=run_id, article_id=article_id)
    return await build_step_context(
        settings=settings, sessionmaker=sessionmaker, gateway=gateway, prompts=prompts, call=call
    )
