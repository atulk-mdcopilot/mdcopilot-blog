import pickle

import pytest

from mdcopilot_blog.domain.errors import (
    ArticleStructureError,
    DomainError,
    InsufficientEvidence,
    OutputRejected,
    PublishingDisabled,
    UnknownCitationMarker,
)


def test_errors_derive_from_domain_error() -> None:
    for cls in (InsufficientEvidence, ArticleStructureError, UnknownCitationMarker, PublishingDisabled, OutputRejected):
        assert issubclass(cls, DomainError)
    assert issubclass(DomainError, Exception)


@pytest.mark.parametrize(
    "instance",
    [
        InsufficientEvidence("rr-1", 3, 5, 4),
        ArticleStructureError("expected 6 H2 sections, found 5"),
        UnknownCitationMarker(["S9", "S12"]),
        PublishingDisabled("publishing is disabled"),
        OutputRejected("unknown markers: S9"),
    ],
)
def test_errors_pickle_round_trip(instance: Exception) -> None:
    restored = pickle.loads(pickle.dumps(instance))
    assert type(restored) is type(instance)
    assert restored.args == instance.args
    assert str(restored) == str(instance)


def test_messages_and_attributes() -> None:
    exc = InsufficientEvidence("rr-1", 3, 5, 4)
    assert str(exc) == "insufficient evidence for research run rr-1: 3 sources (need 5), 4 successful queries"
    assert (exc.research_run_id, exc.found_sources, exc.required_sources, exc.successful_queries) == ("rr-1", 3, 5, 4)

    exc = UnknownCitationMarker(["S9", "S12"])
    assert exc.args == (["S9", "S12"],)
    assert exc.markers == ["S9", "S12"]
    assert str(exc) == "unknown markers: S9, S12"

    assert str(ArticleStructureError("expected 6 H2 sections, found 5")) == "expected 6 H2 sections, found 5"
    assert str(PublishingDisabled("publishing is disabled")) == "publishing is disabled"
    assert str(OutputRejected("unknown markers: S9")) == "unknown markers: S9"
