"""Status transition tables (ARCHITECTURE §6): every listed move is allowed, every other move raises."""

import pickle
from collections import deque
from enum import StrEnum
from typing import cast

import pytest

from mdcopilot_blog.domain.enums import ArticleStatus, PublicationStatus, RunStatus
from mdcopilot_blog.domain.state_machine import (
    TRANSITIONS,
    Entity,
    InvalidTransition,
    can_transition,
    require_transition,
)

# The contract table, written out independently of the implementation.
EXPECTED: dict[Entity, dict[str, set[str]]] = {
    Entity.RUN: {
        RunStatus.QUEUED: {RunStatus.RESEARCHING, RunStatus.PRODUCING, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.RESEARCHING: {RunStatus.TOPICS_READY, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.TOPICS_READY: {
            RunStatus.WAITING_FOR_TOPIC,
            RunStatus.PRODUCING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        },
        RunStatus.WAITING_FOR_TOPIC: {
            RunStatus.TOPICS_READY,
            RunStatus.PRODUCING,
            RunStatus.FAILED,
            RunStatus.CANCELLED,
        },
        RunStatus.PRODUCING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.SUCCEEDED: {RunStatus.QUEUED},
        RunStatus.FAILED: {RunStatus.QUEUED},
        RunStatus.CANCELLED: {RunStatus.QUEUED},
    },
    Entity.ARTICLE: {
        ArticleStatus.DRAFTING: {ArticleStatus.FACT_CHECKING, ArticleStatus.FAILED, ArticleStatus.SUPERSEDED},
        ArticleStatus.FACT_CHECKING: {
            ArticleStatus.CLINICAL_REVIEW,
            ArticleStatus.SEO,
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.CLINICAL_REVIEW: {
            ArticleStatus.EDITORIAL_REVIEW,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.EDITORIAL_REVIEW: {
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SEO,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.SEO: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.READY_FOR_REVIEW: {
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.QUALITY_GATE_FAILED,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.QUALITY_GATE_FAILED: {
            ArticleStatus.READY_FOR_REVIEW,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SUPERSEDED,
        },
        ArticleStatus.APPROVED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.SCHEDULED,
            ArticleStatus.REJECTED,
            ArticleStatus.DRAFTING,
            ArticleStatus.READY_FOR_REVIEW,
        },
        ArticleStatus.SCHEDULED: {
            ArticleStatus.EXPORTED,
            ArticleStatus.PUBLISHING,
            ArticleStatus.APPROVED,
            ArticleStatus.REJECTED,
        },
        ArticleStatus.EXPORTED: {ArticleStatus.PUBLISHED, ArticleStatus.REJECTED},
        ArticleStatus.PUBLISHING: {ArticleStatus.PUBLISHED, ArticleStatus.PUBLISH_FAILED},
        ArticleStatus.PUBLISH_FAILED: {ArticleStatus.PUBLISHING, ArticleStatus.APPROVED},
        ArticleStatus.FAILED: {ArticleStatus.DRAFTING, ArticleStatus.SUPERSEDED},
        ArticleStatus.PUBLISHED: set(),
        ArticleStatus.REJECTED: set(),
        ArticleStatus.SUPERSEDED: set(),
    },
    Entity.PUBLICATION: {
        PublicationStatus.PENDING: {PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS},
        PublicationStatus.EXPORTED: {PublicationStatus.CONFIRMED},
        PublicationStatus.CONFIRMED: set(),
        PublicationStatus.IN_PROGRESS: {PublicationStatus.PUBLISHED, PublicationStatus.FAILED},
        PublicationStatus.PUBLISHED: set(),
        PublicationStatus.FAILED: {PublicationStatus.IN_PROGRESS},
    },
}

STATUS_ENUMS: dict[Entity, type[StrEnum]] = {
    Entity.RUN: RunStatus,
    Entity.ARTICLE: ArticleStatus,
    Entity.PUBLICATION: PublicationStatus,
}

# States with no way out. Run end states are not here: they can be re-queued (restart).
TERMINAL: set[tuple[Entity, str]] = {
    (Entity.ARTICLE, ArticleStatus.PUBLISHED),
    (Entity.ARTICLE, ArticleStatus.REJECTED),
    (Entity.ARTICLE, ArticleStatus.SUPERSEDED),
    (Entity.PUBLICATION, PublicationStatus.CONFIRMED),
    (Entity.PUBLICATION, PublicationStatus.PUBLISHED),
}

# Article states an agent workflow can leave an article in (no human has approved it yet).
AGENT_STATES: set[str] = {
    ArticleStatus.DRAFTING,
    ArticleStatus.FACT_CHECKING,
    ArticleStatus.CLINICAL_REVIEW,
    ArticleStatus.EDITORIAL_REVIEW,
    ArticleStatus.SEO,
    ArticleStatus.READY_FOR_REVIEW,
    ArticleStatus.QUALITY_GATE_FAILED,
    ArticleStatus.FAILED,
}
AFTER_APPROVAL: set[str] = {
    ArticleStatus.SCHEDULED,
    ArticleStatus.EXPORTED,
    ArticleStatus.PUBLISHING,
    ArticleStatus.PUBLISH_FAILED,
    ArticleStatus.PUBLISHED,
}

ALLOWED = [
    pytest.param(entity, current, target, id=f"{entity}:{current}->{target}")
    for entity, table in EXPECTED.items()
    for current, targets in table.items()
    for target in sorted(targets)
]
ILLEGAL = [
    pytest.param(entity, current.value, target.value, id=f"{entity}:{current}->{target}")
    for entity, status_enum in STATUS_ENUMS.items()
    for current in status_enum
    for target in status_enum
    if current != target and target not in EXPECTED[entity][current]
]
SAME_STATE = [
    pytest.param(entity, state.value, id=f"{entity}:{state}")
    for entity, status_enum in STATUS_ENUMS.items()
    for state in status_enum
]
# Named examples of moves that must never happen; each is also covered by ILLEGAL.
REPRESENTATIVE_ILLEGAL = [
    pytest.param(Entity.RUN, RunStatus.QUEUED, RunStatus.SUCCEEDED, id="run-skips-all-work"),
    pytest.param(Entity.RUN, RunStatus.RESEARCHING, RunStatus.WAITING_FOR_TOPIC, id="run-waits-before-topics"),
    pytest.param(Entity.RUN, RunStatus.SUCCEEDED, RunStatus.CANCELLED, id="run-cancel-after-success"),
    pytest.param(Entity.RUN, RunStatus.FAILED, RunStatus.CANCELLED, id="run-cancel-after-failure"),
    pytest.param(Entity.RUN, RunStatus.CANCELLED, RunStatus.PRODUCING, id="run-resume-without-requeue"),
    pytest.param(Entity.RUN, RunStatus.WAITING_FOR_TOPIC, RunStatus.SUCCEEDED, id="run-succeeds-while-waiting"),
    pytest.param(Entity.ARTICLE, ArticleStatus.DRAFTING, ArticleStatus.APPROVED, id="article-draft-self-approves"),
    pytest.param(Entity.ARTICLE, ArticleStatus.SEO, ArticleStatus.PUBLISHING, id="article-seo-publishes"),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.READY_FOR_REVIEW, ArticleStatus.EXPORTED, id="article-export-unapproved"
    ),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.READY_FOR_REVIEW, ArticleStatus.PUBLISHED, id="article-publish-unapproved"
    ),
    pytest.param(
        Entity.ARTICLE, ArticleStatus.QUALITY_GATE_FAILED, ArticleStatus.SCHEDULED, id="article-schedule-unapproved"
    ),
    pytest.param(Entity.ARTICLE, ArticleStatus.EXPORTED, ArticleStatus.APPROVED, id="article-unexport"),
    pytest.param(Entity.ARTICLE, ArticleStatus.PUBLISHING, ArticleStatus.REJECTED, id="article-reject-mid-publish"),
    pytest.param(Entity.ARTICLE, ArticleStatus.PUBLISHED, ArticleStatus.DRAFTING, id="article-edit-after-publish"),
    pytest.param(Entity.ARTICLE, ArticleStatus.REJECTED, ArticleStatus.APPROVED, id="article-approve-rejected"),
    pytest.param(Entity.ARTICLE, ArticleStatus.SUPERSEDED, ArticleStatus.DRAFTING, id="article-revive-superseded"),
    pytest.param(Entity.ARTICLE, ArticleStatus.FAILED, ArticleStatus.READY_FOR_REVIEW, id="article-failed-to-review"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.PENDING, PublicationStatus.PUBLISHED, id="pub-skip-in-progress"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS, id="pub-switch-mode"),
    pytest.param(Entity.PUBLICATION, PublicationStatus.CONFIRMED, PublicationStatus.PENDING, id="pub-reopen"),
    pytest.param(
        Entity.PUBLICATION, PublicationStatus.PUBLISHED, PublicationStatus.FAILED, id="pub-fail-after-success"
    ),
]


def _as_sets(entity: Entity) -> dict[str, set[str]]:
    return {state: set(targets) for state, targets in TRANSITIONS[entity].items()}


def test_run_status_values() -> None:
    assert [status.value for status in RunStatus] == [
        "QUEUED",
        "RESEARCHING",
        "TOPICS_READY",
        "WAITING_FOR_TOPIC",
        "PRODUCING",
        "SUCCEEDED",
        "FAILED",
        "CANCELLED",
    ]


def test_article_status_values() -> None:
    assert [status.value for status in ArticleStatus] == [
        "DRAFTING",
        "FACT_CHECKING",
        "CLINICAL_REVIEW",
        "EDITORIAL_REVIEW",
        "SEO",
        "READY_FOR_REVIEW",
        "QUALITY_GATE_FAILED",
        "APPROVED",
        "SCHEDULED",
        "EXPORTED",
        "PUBLISHING",
        "PUBLISHED",
        "PUBLISH_FAILED",
        "REJECTED",
        "FAILED",
        "SUPERSEDED",
    ]


def test_publication_status_values() -> None:
    assert [status.value for status in PublicationStatus] == [
        "PENDING",
        "EXPORTED",
        "CONFIRMED",
        "IN_PROGRESS",
        "PUBLISHED",
        "FAILED",
    ]


def test_entity_values() -> None:
    assert [entity.value for entity in Entity] == ["run", "article", "publication"]


def test_expected_table_is_complete_and_well_formed() -> None:
    assert set(EXPECTED) == set(Entity)
    for entity, status_enum in STATUS_ENUMS.items():
        members = {state.value for state in status_enum}
        assert set(EXPECTED[entity]) == members
        assert all(targets <= members for targets in EXPECTED[entity].values())
    edge_counts = {entity: sum(len(targets) for targets in table.values()) for entity, table in EXPECTED.items()}
    assert edge_counts == {Entity.RUN: 21, Entity.ARTICLE: 53, Entity.PUBLICATION: 6}
    assert (len(ALLOWED), len(ILLEGAL), len(SAME_STATE)) == (80, 246, 30)


@pytest.mark.parametrize("entity", list(Entity))
def test_table_matches_contract_exactly(entity: Entity) -> None:
    assert _as_sets(entity) == EXPECTED[entity]


@pytest.mark.parametrize(("entity", "current", "target"), ALLOWED)
def test_listed_transition_is_allowed(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is True
    require_transition(entity, current, target)


@pytest.mark.parametrize(("entity", "current", "target"), ILLEGAL)
def test_unlisted_transition_is_rejected(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is False
    with pytest.raises(InvalidTransition) as caught:
        require_transition(entity, current, target)
    assert (caught.value.entity, caught.value.current, caught.value.target) == (entity, current, target)


@pytest.mark.parametrize(("entity", "current", "target"), REPRESENTATIVE_ILLEGAL)
def test_representative_illegal_transition_raises(entity: Entity, current: str, target: str) -> None:
    assert target not in EXPECTED[entity][current]
    with pytest.raises(InvalidTransition, match=f"^illegal {entity} transition: {current} -> {target}$"):
        require_transition(entity, current, target)


@pytest.mark.parametrize(("entity", "state"), SAME_STATE)
def test_same_state_is_a_noop(entity: Entity, state: str) -> None:
    assert can_transition(entity, state, state) is True
    require_transition(entity, state, state)


@pytest.mark.parametrize(("entity", "state"), sorted(TERMINAL))
def test_terminal_state_has_no_exits(entity: Entity, state: str) -> None:
    assert TRANSITIONS[entity][state] == frozenset()
    for target in STATUS_ENUMS[entity]:
        if target != state:
            assert can_transition(entity, state, target) is False


def test_terminal_states_are_exactly_the_listed_ones() -> None:
    no_exit = {(entity, state) for entity in Entity for state, targets in TRANSITIONS[entity].items() if not targets}
    assert no_exit == TERMINAL


@pytest.mark.parametrize("state", [RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED])
def test_finished_run_can_only_be_requeued(state: RunStatus) -> None:
    assert TRANSITIONS[Entity.RUN][state] == frozenset({RunStatus.QUEUED})


def test_every_publish_path_goes_through_human_approval() -> None:
    graph = _as_sets(Entity.ARTICLE)
    reachable: set[str] = set()
    queue = deque(AGENT_STATES)
    while queue:
        state = queue.popleft()
        for target in graph[state]:
            if target != ArticleStatus.APPROVED and target not in reachable:
                reachable.add(target)
                queue.append(target)
    assert reachable.isdisjoint(AFTER_APPROVAL)


@pytest.mark.parametrize(
    ("entity", "current", "target"),
    [
        pytest.param(Entity.RUN, "BOGUS", RunStatus.QUEUED, id="unknown-current"),
        pytest.param(Entity.RUN, RunStatus.QUEUED, "BOGUS", id="unknown-target"),
        pytest.param(Entity.RUN, "BOGUS", "BOGUS", id="unknown-same-state"),
        pytest.param(Entity.RUN, "queued", "researching", id="wrong-case"),
        pytest.param(Entity.PUBLICATION, ArticleStatus.DRAFTING, ArticleStatus.DRAFTING, id="other-entity-state"),
        pytest.param(Entity.RUN, ArticleStatus.DRAFTING, RunStatus.QUEUED, id="article-state-on-run"),
    ],
)
def test_unknown_states_are_rejected(entity: Entity, current: str, target: str) -> None:
    assert can_transition(entity, current, target) is False
    with pytest.raises(InvalidTransition):
        require_transition(entity, current, target)


def test_plain_strings_from_the_database_are_accepted() -> None:
    assert can_transition(Entity.RUN, "QUEUED", "RESEARCHING") is True
    assert can_transition(Entity.ARTICLE, "APPROVED", "EXPORTED") is True
    assert can_transition(Entity.PUBLICATION, "IN_PROGRESS", "PUBLISHED") is True


def test_invalid_transition_details() -> None:
    with pytest.raises(InvalidTransition) as caught:
        require_transition(Entity.RUN, RunStatus.SUCCEEDED, RunStatus.CANCELLED)
    error = caught.value
    assert isinstance(error, ValueError)
    assert error.entity is Entity.RUN
    assert error.current == "SUCCEEDED"
    assert error.target == "CANCELLED"
    assert type(error.current) is str
    assert str(error) == "illegal run transition: SUCCEEDED -> CANCELLED"


def test_invalid_transition_survives_pickling() -> None:
    # DBOS stores a failed step's exception with its default (pickle-based) serializer.
    error = InvalidTransition(Entity.ARTICLE, "PUBLISHED", "DRAFTING")
    restored = pickle.loads(pickle.dumps(error))
    assert isinstance(restored, InvalidTransition)
    assert (restored.entity, restored.current, restored.target) == (Entity.ARTICLE, "PUBLISHED", "DRAFTING")
    assert str(restored) == str(error)


def test_waiting_for_topic_can_fail() -> None:
    assert can_transition(Entity.RUN, "WAITING_FOR_TOPIC", "FAILED") is True
    require_transition(Entity.RUN, "WAITING_FOR_TOPIC", "FAILED")


def test_fact_checking_can_return_to_drafting() -> None:
    assert can_transition(Entity.ARTICLE, "FACT_CHECKING", "DRAFTING") is True
    require_transition(Entity.ARTICLE, "FACT_CHECKING", "DRAFTING")


def test_failed_article_can_be_superseded() -> None:
    assert can_transition(Entity.ARTICLE, "FAILED", "SUPERSEDED") is True
    require_transition(Entity.ARTICLE, "FAILED", "SUPERSEDED")


def test_tables_are_read_only() -> None:
    with pytest.raises(TypeError):
        cast(dict[Entity, object], TRANSITIONS)[Entity.RUN] = {}
    with pytest.raises(TypeError):
        cast(dict[str, frozenset[str]], TRANSITIONS[Entity.RUN])[RunStatus.QUEUED] = frozenset()
