"""Admin user management (blog.settings)."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy import select

from mdcopilot_blog.api.deps import Principal, SessionDep, require_permission, utcnow
from mdcopilot_blog.api.schemas import UserCreate, UserOut, UserUpdate
from mdcopilot_blog.auth.sessions import revoke_user_sessions
from mdcopilot_blog.auth.users import UserExists, create_user, set_password
from mdcopilot_blog.db.models import User
from mdcopilot_blog.domain.enums import Permission
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit

router = APIRouter(tags=["users"])

AdminDep = Annotated[Principal, Depends(require_permission(Permission.SETTINGS))]


@router.get("", response_model=list[UserOut])
async def list_users(_: AdminDep, db: SessionDep) -> list[UserOut]:
    users = (await db.scalars(select(User).order_by(User.created_at, User.email))).all()
    return [UserOut.model_validate(user) for user in users]


@router.post("", status_code=201, response_model=UserOut)
async def create_user_route(body: UserCreate, principal: AdminDep, db: SessionDep) -> UserOut:
    try:
        user = await create_user(
            db, email=body.email, display_name=body.display_name, role=body.role, password=body.password
        )
    except UserExists:
        raise ProblemError(409, "User already exists") from None
    except ValueError as exc:
        raise ProblemError(422, "Request validation failed", str(exc)) from None
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="user.create",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "role": user.role},
    )
    await db.commit()
    return UserOut.model_validate(user)


@router.patch("/{user_id}", response_model=UserOut)
async def update_user_route(user_id: uuid.UUID, body: UserUpdate, principal: AdminDep, db: SessionDep) -> UserOut:
    user = await db.get(User, user_id)
    if user is None:
        raise ProblemError(404, "User not found")
    is_self = user.id == principal.user_id
    new_role = body.role.value if body.role is not None else None
    if is_self and new_role is not None and new_role != user.role:
        raise ProblemError(409, "You cannot change your own role")
    if is_self and body.is_active is False:
        raise ProblemError(409, "You cannot deactivate yourself")

    now = utcnow()
    changes: dict[str, object] = {}
    if new_role is not None and new_role != user.role:
        changes["role"] = {"from": user.role, "to": new_role}
        user.role = new_role
    if body.is_active is not None and body.is_active != user.is_active:
        changes["is_active"] = {"from": user.is_active, "to": body.is_active}
        user.is_active = body.is_active
        if not body.is_active:
            await revoke_user_sessions(db, user.id, now=now)
    if body.password is not None:
        try:
            await set_password(user, body.password)
        except ValueError as exc:
            raise ProblemError(422, "Request validation failed", str(exc)) from None
        changes["password"] = "changed"
        # Everyone signed in with the old password is signed out, except the admin making the change.
        await revoke_user_sessions(db, user.id, now=now, keep_token=principal.session_token if is_self else None)
    if changes:
        await db.flush()
        await audit(
            db,
            actor_user_id=principal.user_id,
            action="user.update",
            entity_type="user",
            entity_id=str(user.id),
            details=changes,
        )
        await db.commit()
    return UserOut.model_validate(user)
