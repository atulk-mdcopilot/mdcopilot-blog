"""Mock-mode models: Pydantic AI ``FunctionModel`` replaying JSON fixtures.

Importing this module changes no global state; ``build_model_factory`` sets
``models.ALLOW_MODEL_REQUESTS = False`` when mock mode is on.
"""

import copy
import json
from pathlib import Path
from typing import Any

from pydantic_ai import ModelResponse, RequestUsage, ToolCallPart
from pydantic_ai.messages import ModelMessage
from pydantic_ai.models import Model
from pydantic_ai.models.function import AgentInfo, FunctionModel

from mdcopilot_blog.llm.gateway import AgentSpec, ModelFactory
from mdcopilot_blog.llm.routes import ModelChoice

USAGE_KEYS = frozenset({"input_tokens", "output_tokens"})


def default_llm_fixture_root() -> Path:
    """``backend/fixtures/mock/llm`` (editable install), else ``<cwd>/fixtures/mock/llm``."""
    candidate = Path(__file__).resolve().parents[3] / "fixtures" / "mock" / "llm"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "fixtures" / "mock" / "llm"


class FixtureRegistry:
    """Fixtures keyed by (agent, prompt name): ``<root>/<agent>/<prompt_name with '/' -> '_'>.json``."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._cache: dict[tuple[str, str], dict[str, Any]] = {}

    @classmethod
    def default(cls) -> "FixtureRegistry":
        return cls(default_llm_fixture_root())

    def path_for(self, agent: str, prompt_name: str) -> Path:
        return self.root / agent / f"{prompt_name.replace('/', '_')}.json"

    def load(self, agent: str, prompt_name: str) -> dict[str, Any]:
        key = (agent, prompt_name)
        cached = self._cache.get(key)
        if cached is not None:
            return cached
        path = self.path_for(agent, prompt_name)
        if not path.is_file():
            raise FileNotFoundError(f"no mock fixture for agent {agent!r} prompt {prompt_name!r}: expected {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("output"), dict):
            raise TypeError(f"{path}: fixture must be an object with an 'output' object")
        usage = data.get("usage")
        if (
            not isinstance(usage, dict)
            or set(usage) != USAGE_KEYS
            or not all(isinstance(v, int) for v in usage.values())
        ):
            raise ValueError(f"{path}: 'usage' must be {{'input_tokens': int, 'output_tokens': int}}")
        self._cache[key] = data
        return data


class MockModelFactory(ModelFactory):
    """Ignores the provider in ``choice``; every agent replays its fixture."""

    def __init__(self, fixtures: FixtureRegistry) -> None:
        self.fixtures = fixtures

    def build(self, choice: ModelChoice, spec: AgentSpec[Any]) -> Model:
        fixture = self.fixtures.load(spec.name.value, spec.prompt_name)
        output: dict[str, Any] = fixture["output"]
        input_tokens: int = fixture["usage"]["input_tokens"]
        output_tokens: int = fixture["usage"]["output_tokens"]

        async def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
            return ModelResponse(
                parts=[ToolCallPart(info.output_tools[0].name, copy.deepcopy(output))],
                usage=RequestUsage(input_tokens=input_tokens, output_tokens=output_tokens),
            )

        return FunctionModel(respond, model_name=f"mock:{spec.name.value}")
