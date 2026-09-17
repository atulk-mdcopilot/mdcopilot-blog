import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from pydantic import SecretStr, ValidationError

from mdcopilot_blog.api.schemas import (
    ManualRunRequest,
    Page,
    ProviderKeyView,
    RunOut,
    SessionResponse,
    SessionUser,
    UserCreate,
    UserUpdate,
    mask_secret,
)
from mdcopilot_blog.domain.enums import Permission, Role, RunKind, RunStatus


def test_mask_secret() -> None:
    assert mask_secret(None) == ProviderKeyView(configured=False, preview=None)
    assert mask_secret(SecretStr("")) == ProviderKeyView(configured=False, preview=None)
    assert mask_secret(SecretStr("short-key")) == ProviderKeyView(configured=True, preview="set")
    assert mask_secret(SecretStr("sk-abcdefghWXYZ")) == ProviderKeyView(configured=True, preview="sk-…WXYZ")


def test_session_response_is_camel_case() -> None:
    user_id = uuid.uuid4()
    body = SessionResponse(
        user=SessionUser(
            id=user_id, email="a@b.test", display_name="A", role=Role.VIEWER, permissions=[Permission.VIEW]
        ),
        csrf_token="t",
    ).model_dump(mode="json")
    assert body == {
        "user": {
            "id": str(user_id),
            "email": "a@b.test",
            "displayName": "A",
            "role": "viewer",
            "permissions": ["blog.view"],
        },
        "csrfToken": "t",
    }


def test_user_create_validation() -> None:
    ok = UserCreate.model_validate(
        {"email": " New@Example.TEST ", "displayName": " New ", "role": "editor", "password": "x" * 12}
    )
    assert (ok.email, ok.display_name, ok.role) == ("new@example.test", "New", Role.EDITOR)
    bad_inputs = [
        {"email": "no-at-sign", "displayName": "N", "role": "editor", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "   ", "role": "editor", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "N", "role": "owner", "password": "x" * 12},
        {"email": "a@b.test", "displayName": "N", "role": "editor", "password": ""},
        {"email": "a@b.test", "displayName": "N", "role": "editor", "password": "x" * 12, "isAdmin": True},
    ]
    for payload in bad_inputs:
        with pytest.raises(ValidationError):
            UserCreate.model_validate(payload)


def test_user_update_tracks_only_sent_fields() -> None:
    update = UserUpdate.model_validate({"isActive": False})
    assert update.model_fields_set == {"is_active"}
    assert (update.role, update.is_active, update.password) == (None, False, None)


def test_manual_run_request_bounds() -> None:
    assert ManualRunRequest.model_validate({}).model_dump(exclude_none=True) == {}
    req = ManualRunRequest.model_validate({"runDate": "2026-09-17", "pillar": "A", "wordCount": 900})
    assert req.model_dump(mode="json", exclude_none=True) == {"runDate": "2026-09-17", "pillar": "A", "wordCount": 900}
    for payload in ({"wordCount": 299}, {"wordCount": 3001}, {"topic": "x" * 301}, {"pillar": "Z"}, {"extra": 1}):
        with pytest.raises(ValidationError):
            ManualRunRequest.model_validate(payload)


def test_page_of_runs_serializes_camel_case_and_decimal_as_string() -> None:
    run = RunOut(
        id=uuid.uuid4(),
        kind=RunKind.MANUAL,
        run_date=date(2026, 9, 17),
        status=RunStatus.QUEUED,
        stage=None,
        trace_id="a" * 32,
        cost_usd=Decimal("0.001200"),
        created_at=datetime(2026, 9, 17, tzinfo=UTC),
        started_at=None,
        finished_at=None,
    )
    body = Page[RunOut](items=[run], total=1, limit=20, offset=0).model_dump(mode="json")
    assert body["total"] == 1
    item = body["items"][0]
    assert item["costUsd"] == "0.001200"
    assert item["runDate"] == "2026-09-17"
    assert item["traceId"] == "a" * 32
    assert "run_date" not in item
