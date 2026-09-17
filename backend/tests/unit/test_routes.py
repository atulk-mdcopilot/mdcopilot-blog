"""Route parsing and key-based filtering."""

import pytest
from pydantic import SecretStr

from mdcopilot_blog.domain.enums import AgentName
from mdcopilot_blog.llm.routes import ModelChoice, parse_choice, route_for
from mdcopilot_blog.settings import Settings

WRITER_ROUTE = ["openai:gpt-test-sol", "google:gemini-test-flash", "anthropic:claude-test"]


def configure(settings: Settings, *, mock_mode: bool, openai: bool, gemini: bool, anthropic: bool) -> Settings:
    return settings.model_copy(
        update={
            "mock_mode": mock_mode,
            "openai_api_key": SecretStr("sk-test-openai") if openai else None,
            "gemini_api_key": SecretStr("test-gemini") if gemini else None,
            "anthropic_api_key": SecretStr("test-anthropic") if anthropic else None,
            "writer_route": list(WRITER_ROUTE),
        }
    )


def test_parse_choice_valid() -> None:
    choice = parse_choice(" openai : gpt-5.6-sol ")
    assert choice == ModelChoice(provider="openai", model="gpt-5.6-sol")
    assert choice.ref() == "openai:gpt-5.6-sol"
    assert parse_choice("google:gemini-3.8-flash").provider == "google"
    assert parse_choice("anthropic:claude-sonnet-5").provider == "anthropic"
    assert parse_choice("mock:hello") == ModelChoice(provider="mock", model="hello")


@pytest.mark.parametrize("raw", ["gpt-5.6-sol", "openai:", ":gpt-5.6-sol", "", "azure:gpt-5", "OpenAI:gpt-5"])
def test_parse_choice_rejects_bad_entries(raw: str) -> None:
    with pytest.raises(ValueError, match="invalid model route entry"):
        parse_choice(raw)


def test_real_mode_drops_providers_without_keys(settings: Settings) -> None:
    only_openai = configure(settings, mock_mode=False, openai=True, gemini=False, anthropic=False)
    assert route_for(only_openai, AgentName.WRITER) == (ModelChoice("openai", "gpt-test-sol"),)

    no_anthropic = configure(settings, mock_mode=False, openai=True, gemini=True, anthropic=False)
    assert [c.ref() for c in route_for(no_anthropic, AgentName.WRITER)] == [
        "openai:gpt-test-sol",
        "google:gemini-test-flash",
    ]

    all_keys = configure(settings, mock_mode=False, openai=True, gemini=True, anthropic=True)
    assert [c.ref() for c in route_for(all_keys, AgentName.WRITER)] == WRITER_ROUTE


def test_real_mode_with_no_usable_entry_raises(settings: Settings) -> None:
    no_keys = configure(settings, mock_mode=False, openai=False, gemini=False, anthropic=False)
    with pytest.raises(ValueError, match="no usable model route for agent 'writer'"):
        route_for(no_keys, AgentName.WRITER)


def test_mock_mode_returns_route_unfiltered(settings: Settings) -> None:
    no_keys = configure(settings, mock_mode=True, openai=False, gemini=False, anthropic=False)
    assert [c.ref() for c in route_for(no_keys, AgentName.WRITER)] == WRITER_ROUTE


def test_empty_route_raises_even_in_mock_mode(settings: Settings) -> None:
    empty = settings.model_copy(update={"mock_mode": True, "seo_route": []})
    with pytest.raises(ValueError, match="no usable model route for agent 'seo'"):
        route_for(empty, AgentName.SEO)


def test_invalid_entry_in_settings_raises(settings: Settings) -> None:
    broken = settings.model_copy(update={"mock_mode": True, "seo_route": ["gemini-without-provider"]})
    with pytest.raises(ValueError, match="invalid model route entry"):
        route_for(broken, AgentName.SEO)


@pytest.mark.parametrize("mock_mode", [True, False])
def test_hello_route_is_fixed_mock(settings: Settings, mock_mode: bool) -> None:
    configured = configure(settings, mock_mode=mock_mode, openai=False, gemini=False, anthropic=False)
    assert route_for(configured, AgentName.HELLO) == (ModelChoice("mock", "hello"),)


@pytest.mark.parametrize("agent", [a for a in AgentName if a != AgentName.HELLO])
def test_each_agent_reads_its_own_route_field(settings: Settings, agent: AgentName) -> None:
    field = f"{agent.value}_route"
    configured = settings.model_copy(update={"mock_mode": True, field: [f"mock:{agent.value}-model"]})
    assert route_for(configured, agent) == (ModelChoice("mock", f"{agent.value}-model"),)
