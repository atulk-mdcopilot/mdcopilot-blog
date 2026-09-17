"""RBAC matrix (ARCHITECTURE §17): exact permissions per role, deny by default."""

from itertools import pairwise
from typing import cast

import pytest

from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import ROLE_PERMISSIONS, permissions_for

# ARCHITECTURE §17, one row per permission. Columns: viewer, editor, reviewer, publisher, admin ("X" = granted).
SPEC_MATRIX: dict[Permission, str] = {
    Permission.VIEW: "XXXXX",
    Permission.GENERATE: ".XXXX",
    Permission.EDIT: ".XXXX",
    Permission.REVIEW: "..XXX",
    Permission.APPROVE: "..XXX",
    Permission.SCHEDULE: "..XXX",
    Permission.PUBLISH: "...XX",
    Permission.AGENT_RUNS: "..XXX",
    Permission.SETTINGS: "....X",
}
ROLE_COLUMNS: tuple[Role, ...] = (Role.VIEWER, Role.EDITOR, Role.REVIEWER, Role.PUBLISHER, Role.ADMIN)

EXPECTED: dict[Role, set[Permission]] = {
    Role.VIEWER: {Permission.VIEW},
    Role.EDITOR: {Permission.VIEW, Permission.GENERATE, Permission.EDIT},
    Role.REVIEWER: {
        Permission.VIEW,
        Permission.GENERATE,
        Permission.EDIT,
        Permission.REVIEW,
        Permission.APPROVE,
        Permission.SCHEDULE,
        Permission.AGENT_RUNS,
    },
    Role.PUBLISHER: {
        Permission.VIEW,
        Permission.GENERATE,
        Permission.EDIT,
        Permission.REVIEW,
        Permission.APPROVE,
        Permission.SCHEDULE,
        Permission.AGENT_RUNS,
        Permission.PUBLISH,
    },
    Role.ADMIN: set(Permission),
}

MATRIX_CELLS = [
    pytest.param(role, permission, SPEC_MATRIX[permission][column] == "X", id=f"{role}-{permission}")
    for permission in Permission
    for column, role in enumerate(ROLE_COLUMNS)
]


def test_role_values_match_the_wire_contract() -> None:
    assert [role.value for role in Role] == ["viewer", "editor", "reviewer", "publisher", "admin"]


def test_permission_values_match_the_wire_contract() -> None:
    assert {permission.name: permission.value for permission in Permission} == {
        "VIEW": "blog.view",
        "GENERATE": "blog.generate",
        "EDIT": "blog.edit",
        "REVIEW": "blog.review",
        "APPROVE": "blog.approve",
        "SCHEDULE": "blog.schedule",
        "PUBLISH": "blog.publish",
        "AGENT_RUNS": "blog.agent_runs",
        "SETTINGS": "blog.settings",
    }


def test_spec_matrix_covers_every_permission_and_role() -> None:
    assert set(SPEC_MATRIX) == set(Permission)
    assert set(ROLE_COLUMNS) == set(Role)
    assert all(len(row) == len(ROLE_COLUMNS) for row in SPEC_MATRIX.values())


def test_every_role_has_an_entry() -> None:
    assert set(ROLE_PERMISSIONS) == set(Role)


@pytest.mark.parametrize("role", list(Role))
def test_role_permissions_are_exact(role: Role) -> None:
    granted = permissions_for(role)
    assert isinstance(granted, frozenset)
    assert granted == EXPECTED[role]
    assert ROLE_PERMISSIONS[role] == EXPECTED[role]


@pytest.mark.parametrize(("role", "permission", "granted"), MATRIX_CELLS)
def test_matrix_cell_matches_spec_table(role: Role, permission: Permission, granted: bool) -> None:
    assert (permission in permissions_for(role)) is granted


def test_roles_are_strictly_nested() -> None:
    chain = [permissions_for(role) for role in ROLE_COLUMNS]
    for lower, higher in pairwise(chain):
        assert lower < higher


def test_admin_has_every_permission() -> None:
    assert permissions_for(Role.ADMIN) == frozenset(Permission)


def test_only_admin_manages_settings_and_users() -> None:
    assert {role for role in Role if Permission.SETTINGS in permissions_for(role)} == {Role.ADMIN}


def test_role_read_from_the_database_as_plain_string_resolves() -> None:
    assert permissions_for(cast(Role, "reviewer")) == EXPECTED[Role.REVIEWER]


def test_unknown_role_gets_no_permissions() -> None:
    assert permissions_for(cast(Role, "superuser")) == frozenset()


def test_matrix_is_read_only() -> None:
    with pytest.raises(TypeError):
        cast(dict[Role, frozenset[Permission]], ROLE_PERMISSIONS)[Role.VIEWER] = frozenset(Permission)
