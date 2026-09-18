"""Role to permission matrix. Deny by default."""

from collections.abc import Mapping
from types import MappingProxyType

from mdcopilot_blog.domain.enums import Permission, Role

_VIEWER: frozenset[Permission] = frozenset({Permission.VIEW})
_EDITOR: frozenset[Permission] = _VIEWER | {Permission.GENERATE, Permission.EDIT}
_REVIEWER: frozenset[Permission] = _EDITOR | {
    Permission.REVIEW,
    Permission.APPROVE,
    Permission.SCHEDULE,
    Permission.AGENT_RUNS,
}
_PUBLISHER: frozenset[Permission] = _REVIEWER | {Permission.PUBLISH}
_ADMIN: frozenset[Permission] = frozenset(Permission)

ROLE_PERMISSIONS: Mapping[Role, frozenset[Permission]] = MappingProxyType(
    {
        Role.VIEWER: _VIEWER,
        Role.EDITOR: _EDITOR,
        Role.REVIEWER: _REVIEWER,
        Role.PUBLISHER: _PUBLISHER,
        Role.ADMIN: _ADMIN,
    }
)


def permissions_for(role: Role) -> frozenset[Permission]:
    """Return the permissions granted to ``role``.

    A role string read from the database works too (``StrEnum`` members hash like their values).
    An unknown role gets no permissions.
    """
    return ROLE_PERMISSIONS.get(role, frozenset())
