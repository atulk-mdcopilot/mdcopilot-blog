"""Prompt registry: loading rules, rendering, version selection, hashing (no database)."""

import hashlib
from pathlib import Path

import pytest

from mdcopilot_blog.prompts.registry import (
    PromptRegistry,
    PromptRegistryError,
    RenderedPrompt,
    default_prompt_root,
)


def write_prompt(
    root: Path,
    relative: str,
    *,
    name: str,
    version: int,
    agent: str,
    variables: list[str],
    body: str,
    output: str = "DraftOutput",
) -> Path:
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    variable_lines = "".join(f"  - {v}\n" for v in variables) if variables else ""
    variables_block = f"variables:\n{variable_lines}" if variables else "variables: []\n"
    path.write_text(
        f"---\nname: {name}\nversion: {version}\nagent: {agent}\noutput: {output}\n{variables_block}---\n{body}",
        encoding="utf-8",
    )
    return path


def test_loads_valid_prompt_and_renders(tmp_path: Path) -> None:
    path = write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["brand_name", "topic"],
        body="Write for {{ brand_name }} about {{ topic }}.\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)

    template = registry.get("writer/draft")
    assert template.name == "writer/draft"
    assert template.version == 1
    assert template.agent == "writer"
    assert template.output == "DraftOutput"
    assert template.variables == ("brand_name", "topic")
    assert template.body == "Write for {{ brand_name }} about {{ topic }}.\n"
    assert template.path == path
    assert template.sha256 == hashlib.sha256(path.read_bytes()).hexdigest()

    rendered = registry.render("writer/draft", {"brand_name": "MDCopilot", "topic": "burnout"})
    assert rendered == RenderedPrompt(
        name="writer/draft",
        version=1,
        sha256=template.sha256,
        text="Write for MDCopilot about burnout.\n",
    )


def test_filename_must_match_name_and_version(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v2.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="static\n",
    )
    with pytest.raises(PromptRegistryError, match=r"filename must be 'draft\.v1\.md'"):
        PromptRegistry.from_directory(tmp_path)


def test_file_must_live_under_agent_directory(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "seo/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="static\n",
    )
    with pytest.raises(PromptRegistryError, match="must live under"):
        PromptRegistry.from_directory(tmp_path)


def test_declared_variables_must_match_template(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="{{ topic }} for {{ audience }}\n",
    )
    with pytest.raises(PromptRegistryError, match="do not match"):
        PromptRegistry.from_directory(tmp_path)


def test_missing_front_matter_key_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "writer" / "draft.v1.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\nname: writer/draft\nversion: 1\nagent: writer\n---\nbody\n", encoding="utf-8")
    with pytest.raises(PromptRegistryError, match="missing keys"):
        PromptRegistry.from_directory(tmp_path)


def test_duplicate_name_and_version_is_rejected(tmp_path: Path) -> None:
    for relative in ("writer/draft.v1.md", "writer/archive/draft.v1.md"):
        write_prompt(
            tmp_path,
            relative,
            name="writer/draft",
            version=1,
            agent="writer",
            variables=[],
            body="static\n",
        )
    with pytest.raises(PromptRegistryError, match="duplicate prompt writer/draft v1"):
        PromptRegistry.from_directory(tmp_path)


def test_render_rejects_missing_and_extra_variables(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="About {{ topic }}\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)
    with pytest.raises(PromptRegistryError, match=r"missing variables \['topic'\]"):
        registry.render("writer/draft", {})
    with pytest.raises(PromptRegistryError, match=r"unexpected variables \['tone'\]"):
        registry.render("writer/draft", {"topic": "x", "tone": "warm"})


def test_render_strict_undefined_attribute_raises(tmp_path: Path) -> None:
    write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=["topic"],
        body="Headline: {{ topic.headline }}\n",
    )
    registry = PromptRegistry.from_directory(tmp_path)
    with pytest.raises(PromptRegistryError, match="headline"):
        registry.render("writer/draft", {"topic": "a plain string has no headline"})
    rendered = registry.render("writer/draft", {"topic": {"headline": "Burnout"}})
    assert rendered.text == "Headline: Burnout\n"


def test_get_returns_latest_version_unless_pinned(tmp_path: Path) -> None:
    for version in (1, 2, 10):
        write_prompt(
            tmp_path,
            f"writer/draft.v{version}.md",
            name="writer/draft",
            version=version,
            agent="writer",
            variables=[],
            body=f"version {version}\n",
        )
    registry = PromptRegistry.from_directory(tmp_path)
    assert registry.get("writer/draft").version == 10
    assert registry.get("writer/draft", version=2).body == "version 2\n"
    assert registry.render("writer/draft", {}, version=1).text == "version 1\n"
    with pytest.raises(PromptRegistryError, match="unknown prompt writer/draft v3"):
        registry.get("writer/draft", version=3)
    with pytest.raises(PromptRegistryError, match="unknown prompt writer/missing"):
        registry.get("writer/missing")


def test_sha_is_stable_and_tracks_file_bytes(tmp_path: Path) -> None:
    path = write_prompt(
        tmp_path,
        "writer/draft.v1.md",
        name="writer/draft",
        version=1,
        agent="writer",
        variables=[],
        body="same text\n",
    )
    first = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    second = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    assert first == second

    path.write_text(path.read_text(encoding="utf-8") + "one more line\n", encoding="utf-8")
    changed = PromptRegistry.from_directory(tmp_path).get("writer/draft").sha256
    assert changed != first
    assert changed == hashlib.sha256(path.read_bytes()).hexdigest()


def test_missing_root_is_an_error(tmp_path: Path) -> None:
    with pytest.raises(PromptRegistryError, match="does not exist"):
        PromptRegistry.from_directory(tmp_path / "nope")


def test_default_root_loads_hello_echo() -> None:
    registry = PromptRegistry.from_directory(default_prompt_root())
    template = registry.get("hello/echo")
    assert template.version == 1
    assert template.agent == "hello"
    assert template.output == "EchoOutput"
    assert template.variables == ("brand_name", "topic")
    rendered = registry.render("hello/echo", {"brand_name": "MDCopilot", "topic": "hello"})
    assert "MDCopilot" in rendered.text
    assert "hello" in rendered.text
