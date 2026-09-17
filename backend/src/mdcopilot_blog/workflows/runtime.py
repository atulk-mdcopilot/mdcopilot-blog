"""Process-wide dependencies for workflow steps.

DBOS steps receive only serialisable arguments, so engine, sessionmaker, prompt registry and gateway
live in one module-level WorkerRuntime that the worker (or the test fixture) sets before DBOS.launch().
"""

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from mdcopilot_blog.db.engine import make_engine, make_sessionmaker
from mdcopilot_blog.llm.gateway import LLMGateway, build_gateway
from mdcopilot_blog.prompts.registry import PromptRegistry, default_prompt_root
from mdcopilot_blog.settings import Settings


@dataclass
class WorkerRuntime:
    settings: Settings
    engine: AsyncEngine
    sessionmaker: async_sessionmaker[AsyncSession]
    prompts: PromptRegistry
    gateway: LLMGateway


_runtime: WorkerRuntime | None = None


def set_runtime(rt: WorkerRuntime | None) -> None:
    global _runtime  # one runtime per worker process, set once at startup
    _runtime = rt


def get_runtime() -> WorkerRuntime:
    if _runtime is None:
        raise RuntimeError("worker runtime is not initialised; call set_runtime() before running workflows")
    return _runtime


async def build_runtime(settings: Settings) -> WorkerRuntime:
    engine = make_engine(settings.database_url())
    sessionmaker = make_sessionmaker(engine)
    prompts = PromptRegistry.from_directory(default_prompt_root())
    gateway = build_gateway(settings, sessionmaker, prompts)
    return WorkerRuntime(settings=settings, engine=engine, sessionmaker=sessionmaker, prompts=prompts, gateway=gateway)
