"""Status transition tables for runs, articles and publications (ARCHITECTURE §6).

The API and the workflows both call ``require_transition`` before writing a status.
Moving to the state an entity is already in is always allowed and changes nothing, so a retried
or forked step can repeat its status write safely.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from mdcopilot_blog.domain.enums import ArticleStatus, PublicationStatus, RunStatus


class Entity(StrEnum):
    """Things that have a status."""

    RUN = "run"
    ARTICLE = "article"
    PUBLICATION = "publication"


class InvalidTransition(ValueError):
    """Raised when a status change is not in the transition table."""

    def __init__(self, entity: Entity, current: str, target: str) -> None:
        # Keep every constructor argument in ``args`` so the exception pickles (DBOS stores step errors).
        super().__init__(entity, current, target)
        self.entity = entity
        self.current = current
        self.target = target

    def __str__(self) -> str:
        return f"illegal {self.entity} transition: {self.current} -> {self.target}"


def _table(edges: Mapping[str, Iterable[str]]) -> Mapping[str, frozenset[str]]:
    return MappingProxyType({state: frozenset(targets) for state, targets in edges.items()})


_RUN = _table(
    {
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
        # Finished runs can only be queued again (restart / retry creates a new attempt).
        RunStatus.SUCCEEDED: {RunStatus.QUEUED},
        RunStatus.FAILED: {RunStatus.QUEUED},
        RunStatus.CANCELLED: {RunStatus.QUEUED},
    }
)

_ARTICLE = _table(
    {
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
        # Only a human approval leads to scheduling, export or publishing.
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
        # Terminal.
        ArticleStatus.PUBLISHED: set(),
        ArticleStatus.REJECTED: set(),
        ArticleStatus.SUPERSEDED: set(),
    }
)

_PUBLICATION = _table(
    {
        PublicationStatus.PENDING: {PublicationStatus.EXPORTED, PublicationStatus.IN_PROGRESS},
        PublicationStatus.EXPORTED: {PublicationStatus.CONFIRMED},
        PublicationStatus.IN_PROGRESS: {PublicationStatus.PUBLISHED, PublicationStatus.FAILED},
        PublicationStatus.FAILED: {PublicationStatus.IN_PROGRESS},
        # Terminal.
        PublicationStatus.CONFIRMED: set(),
        PublicationStatus.PUBLISHED: set(),
    }
)

TRANSITIONS: Mapping[Entity, Mapping[str, frozenset[str]]] = MappingProxyType(
    {Entity.RUN: _RUN, Entity.ARTICLE: _ARTICLE, Entity.PUBLICATION: _PUBLICATION}
)


def can_transition(entity: Entity, current: str, target: str) -> bool:
    """Return True if ``entity`` may move from ``current`` to ``target``.

    Same-state is True (a no-op) for any known state. Unknown states are never allowed.
    """
    table = TRANSITIONS[Entity(entity)]
    if current not in table or target not in table:
        return False
    return current == target or target in table[current]


def require_transition(entity: Entity, current: str, target: str) -> None:
    """Raise ``InvalidTransition`` unless ``can_transition`` allows the move."""
    if not can_transition(entity, current, target):
        raise InvalidTransition(Entity(entity), str(current), str(target))
