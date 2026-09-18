"""Versioned prompt files: load, validate, render, and register in ``blog_prompt_versions``.

Layout: ``backend/prompts/<agent>/<name-last-segment>.v<version>.md`` with YAML front matter
between the first two ``---`` lines. A registered (name, version) whose file bytes changed
without a version bump is refused.
"""

import hashlib
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import jinja2
import yaml
from jinja2 import meta
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mdcopilot_blog.db.models import PromptVersion

REQUIRED_KEYS = frozenset({"name", "version", "agent", "output", "variables"})
FRONT_MATTER_DELIMITER = "---"


class PromptRegistryError(RuntimeError):
    """A prompt file is invalid, missing, or changed without a version bump."""


@dataclass(frozen=True)
class PromptTemplate:
    name: str
    version: int
    agent: str
    output: str
    variables: tuple[str, ...]
    body: str
    sha256: str
    path: Path


@dataclass(frozen=True)
class RenderedPrompt:
    name: str
    version: int
    sha256: str
    text: str


def default_prompt_root() -> Path:
    """``backend/prompts``.

    parents[3] is ``backend/`` for the editable install (dev image, bind mount on /app).
    A non-editable install lives in site-packages, so fall back to ``<cwd>/prompts``
    (the runtime image uses WORKDIR /app and copies ``prompts/`` there).
    """
    candidate = Path(__file__).resolve().parents[3] / "prompts"
    if candidate.is_dir():
        return candidate
    return Path.cwd() / "prompts"


def _make_environment() -> jinja2.Environment:
    # Prompts are plain text for an LLM, not HTML, so autoescape is off on purpose.
    return jinja2.Environment(undefined=jinja2.StrictUndefined, autoescape=False, keep_trailing_newline=True)


def _split_front_matter(path: Path, text: str) -> tuple[dict[str, Any], str]:
    lines = text.splitlines(keepends=True)
    if not lines or lines[0].strip() != FRONT_MATTER_DELIMITER:
        raise PromptRegistryError(f"{path}: file must start with a '---' front matter line")
    for index in range(1, len(lines)):
        if lines[index].strip() == FRONT_MATTER_DELIMITER:
            raw = "".join(lines[1:index])
            body = "".join(lines[index + 1 :]).lstrip("\n")
            break
    else:
        raise PromptRegistryError(f"{path}: front matter is not closed with a second '---' line")
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise PromptRegistryError(f"{path}: front matter is not valid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise PromptRegistryError(f"{path}: front matter must be a YAML mapping")
    return data, body


def _parse_file(root: Path, path: Path, env: jinja2.Environment) -> tuple[PromptTemplate, dict[str, Any]]:
    raw_bytes = path.read_bytes()
    try:
        text = raw_bytes.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise PromptRegistryError(f"{path}: prompt files must be UTF-8") from exc
    front, body = _split_front_matter(path, text)

    missing = REQUIRED_KEYS - front.keys()
    if missing:
        raise PromptRegistryError(f"{path}: front matter is missing keys {sorted(missing)}")
    name, version, agent, output, variables = (
        front["name"],
        front["version"],
        front["agent"],
        front["output"],
        front["variables"],
    )
    if not isinstance(name, str) or not name or any(not part for part in name.split("/")):
        raise PromptRegistryError(f"{path}: 'name' must be a non-empty string like 'agent/prompt'")
    if isinstance(version, bool) or not isinstance(version, int) or version < 1:
        raise PromptRegistryError(f"{path}: 'version' must be a positive integer")
    if not isinstance(agent, str) or not agent:
        raise PromptRegistryError(f"{path}: 'agent' must be a non-empty string")
    if not isinstance(output, str) or not output:
        raise PromptRegistryError(f"{path}: 'output' must be a non-empty string")
    if not isinstance(variables, list) or not all(isinstance(v, str) for v in variables):
        raise PromptRegistryError(f"{path}: 'variables' must be a list of strings")
    if len(set(variables)) != len(variables):
        raise PromptRegistryError(f"{path}: 'variables' contains duplicates")

    expected_filename = f"{name.rsplit('/', 1)[-1]}.v{version}.md"
    if path.name != expected_filename:
        raise PromptRegistryError(f"{path}: filename must be {expected_filename!r} for name={name!r} version={version}")
    relative = path.relative_to(root)
    if len(relative.parts) < 2 or relative.parts[0] != agent:
        raise PromptRegistryError(f"{path}: prompt for agent {agent!r} must live under {root / agent}")

    try:
        parsed = env.parse(body)
    except jinja2.TemplateSyntaxError as exc:
        raise PromptRegistryError(f"{path}: template syntax error: {exc}") from exc
    used = meta.find_undeclared_variables(parsed)
    declared = set(variables)
    if used != declared:
        raise PromptRegistryError(
            f"{path}: declared variables {sorted(declared)} do not match the template's {sorted(used)}"
        )

    template = PromptTemplate(
        name=name,
        version=version,
        agent=agent,
        output=output,
        variables=tuple(variables),
        body=body,
        sha256=hashlib.sha256(raw_bytes).hexdigest(),
        path=path,
    )
    return template, front


class PromptRegistry:
    def __init__(
        self,
        templates: Mapping[tuple[str, int], PromptTemplate],
        front_matter: Mapping[tuple[str, int], Mapping[str, Any]],
    ) -> None:
        self._env = _make_environment()
        self._templates: dict[tuple[str, int], PromptTemplate] = dict(templates)
        self._front_matter: dict[tuple[str, int], dict[str, Any]] = {k: dict(v) for k, v in front_matter.items()}
        self._compiled: dict[tuple[str, int], jinja2.Template] = {
            key: self._env.from_string(t.body) for key, t in self._templates.items()
        }

    @classmethod
    def from_directory(cls, root: Path, *, agents: Collection[str] | None = None) -> "PromptRegistry":
        if not root.is_dir():
            raise PromptRegistryError(f"prompt directory {root} does not exist")
        env = _make_environment()
        templates: dict[tuple[str, int], PromptTemplate] = {}
        front_matter: dict[tuple[str, int], dict[str, Any]] = {}
        if agents is None:
            paths = sorted(root.glob("**/*.v*.md"))
        else:
            paths = sorted(path for agent in agents for path in (root / agent).glob("**/*.v*.md"))
        for path in paths:
            if not path.is_file():
                continue
            template, front = _parse_file(root, path, env)
            key = (template.name, template.version)
            if key in templates:
                raise PromptRegistryError(
                    f"duplicate prompt {template.name} v{template.version}: {templates[key].path} and {path}"
                )
            templates[key] = template
            front_matter[key] = front
        return cls(templates, front_matter)

    def templates(self) -> tuple[PromptTemplate, ...]:
        return tuple(self._templates[key] for key in sorted(self._templates))

    def get(self, name: str, version: int | None = None) -> PromptTemplate:
        if version is not None:
            try:
                return self._templates[(name, version)]
            except KeyError:
                raise PromptRegistryError(f"unknown prompt {name} v{version}") from None
        versions = [v for (n, v) in self._templates if n == name]
        if not versions:
            raise PromptRegistryError(f"unknown prompt {name}")
        return self._templates[(name, max(versions))]

    def render(self, name: str, variables: Mapping[str, object], version: int | None = None) -> RenderedPrompt:
        template = self.get(name, version)
        declared = set(template.variables)
        given = set(variables)
        if given != declared:
            raise PromptRegistryError(
                f"prompt {template.name} v{template.version}: missing variables {sorted(declared - given)}, "
                f"unexpected variables {sorted(given - declared)}"
            )
        compiled = self._compiled[(template.name, template.version)]
        try:
            text = compiled.render(**variables)
        except jinja2.UndefinedError as exc:
            raise PromptRegistryError(f"prompt {template.name} v{template.version}: {exc}") from exc
        return RenderedPrompt(name=template.name, version=template.version, sha256=template.sha256, text=text)

    async def sync_to_db(self, session: AsyncSession) -> int:
        """Insert missing (name, version) rows and commit. Refuse changed text without a version bump."""
        existing_rows = (
            await session.execute(select(PromptVersion.name, PromptVersion.version, PromptVersion.sha256))
        ).all()
        existing = {(row.name, row.version): row.sha256 for row in existing_rows}
        to_insert: list[PromptTemplate] = []
        for template in self.templates():
            key = (template.name, template.version)
            stored_sha = existing.get(key)
            if stored_sha is None:
                to_insert.append(template)
            elif stored_sha != template.sha256:
                raise PromptRegistryError(f"prompt {template.name} v{template.version} changed without a version bump")
        for template in to_insert:
            session.add(
                PromptVersion(
                    name=template.name,
                    version=template.version,
                    agent=template.agent,
                    sha256=template.sha256,
                    body=template.body,
                    front_matter=self._front_matter[(template.name, template.version)],
                )
            )
        await session.commit()
        return len(to_insert)
