"""Status transition tables for runs and articles.

The API and the workflows both call ``require_transition`` before writing a status.
Moving to the state an entity is already in is always allowed and changes nothing, so a retried
step can repeat its status write safely.
"""

from collections.abc import Iterable, Mapping
from enum import StrEnum
from types import MappingProxyType

from mdcopilot_blog.domain.enums import ArticleStatus, RunStatus


class Entity(StrEnum):
    """Things that have a status."""

    RUN = "run"
    ARTICLE = "article"


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
        RunStatus.TOPICS_READY: {RunStatus.PRODUCING, RunStatus.FAILED, RunStatus.CANCELLED},
        RunStatus.PRODUCING: {RunStatus.SUCCEEDED, RunStatus.FAILED, RunStatus.CANCELLED},
        # Terminal.
        RunStatus.SUCCEEDED: set(),
        RunStatus.FAILED: set(),
        RunStatus.CANCELLED: set(),
    }
)

_ARTICLE = _table(
    {
        ArticleStatus.DRAFTING: {ArticleStatus.FACT_CHECKING, ArticleStatus.DRAFT_SAVED, ArticleStatus.FAILED},
        ArticleStatus.FACT_CHECKING: {
            ArticleStatus.CLINICAL_REVIEW,
            ArticleStatus.SEO,
            ArticleStatus.DRAFTING,
            ArticleStatus.DRAFT_SAVED,
            ArticleStatus.FAILED,
        },
        ArticleStatus.CLINICAL_REVIEW: {
            ArticleStatus.EDITORIAL_REVIEW,
            ArticleStatus.DRAFT_SAVED,
            ArticleStatus.FAILED,
        },
        ArticleStatus.EDITORIAL_REVIEW: {
            ArticleStatus.DRAFTING,
            ArticleStatus.FACT_CHECKING,
            ArticleStatus.SEO,
            ArticleStatus.DRAFT_SAVED,
            ArticleStatus.FAILED,
        },
        ArticleStatus.SEO: {
            ArticleStatus.DRAFTING,
            ArticleStatus.DRAFT_SAVED,
            ArticleStatus.FAILED,
        },
        # Terminal: the draft now lives in MDCopilot Blogs.
        ArticleStatus.DRAFT_SAVED: set(),
        ArticleStatus.FAILED: {ArticleStatus.DRAFTING},
    }
)

TRANSITIONS: Mapping[Entity, Mapping[str, frozenset[str]]] = MappingProxyType(
    {Entity.RUN: _RUN, Entity.ARTICLE: _ARTICLE}
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
