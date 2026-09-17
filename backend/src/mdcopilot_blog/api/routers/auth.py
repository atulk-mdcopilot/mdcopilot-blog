"""Login, logout and the current session."""

import uuid

from fastapi import APIRouter, Request, Response

from mdcopilot_blog.api.deps import PrincipalDep, SessionDep, SettingsDep, utcnow
from mdcopilot_blog.api.schemas import LoginRequest, SessionResponse, SessionUser
from mdcopilot_blog.auth.csrf import csrf_token_for
from mdcopilot_blog.auth.rate_limit import login_allowed, record_login_attempt
from mdcopilot_blog.auth.sessions import ABSOLUTE_TIMEOUT, create_session, revoke_session
from mdcopilot_blog.auth.users import authenticate, normalize_email
from mdcopilot_blog.domain.enums import Permission, Role
from mdcopilot_blog.domain.rbac import permissions_for
from mdcopilot_blog.errors import ProblemError
from mdcopilot_blog.services.audit import audit
from mdcopilot_blog.settings import Settings

router = APIRouter(tags=["auth"])


def _session_response(
    *, user_id: uuid.UUID, email: str, display_name: str, role: Role, token: str, settings: Settings
) -> SessionResponse:
    permissions: list[Permission] = sorted(permissions_for(role))
    return SessionResponse(
        user=SessionUser(id=user_id, email=email, display_name=display_name, role=role, permissions=permissions),
        csrf_token=csrf_token_for(token, settings.session_secret.get_secret_value()),
    )


def _client_ip(request: Request) -> str | None:
    # Task 14 runs the api with --no-proxy-headers (no pinned web IP), so request.client is always the
    # direct TCP peer and is never rewritten from X-Forwarded-For. If that ever changes, uvicorn's
    # ProxyHeadersMiddleware must trust only the real proxy's address (never "*" or a whole subnet), or
    # a client can forge a new X-Forwarded-For on each attempt and bypass MAX_FAILURES_PER_IP.
    return request.client.host if request.client else None


@router.post("/login", response_model=SessionResponse)
async def login(
    body: LoginRequest, request: Request, response: Response, db: SessionDep, settings: SettingsDep
) -> SessionResponse:
    now = utcnow()
    email = normalize_email(body.email)
    ip = _client_ip(request)
    if not await login_allowed(db, email=email, ip=ip, now=now):
        raise ProblemError(429, "Too many login attempts")
    user = await authenticate(db, email=email, password=body.password)
    if user is None:
        await record_login_attempt(db, email=email, ip=ip, succeeded=False)
        await db.commit()
        raise ProblemError(401, "Invalid email or password")
    previous = request.cookies.get(settings.session_cookie_name)
    if previous:
        await revoke_session(db, previous, now=now)  # never keep two live sessions for one browser
    token = await create_session(db, user, ip=ip, user_agent=request.headers.get("user-agent"), now=now)
    await record_login_attempt(db, email=email, ip=ip, succeeded=True)
    await audit(db, actor_user_id=user.id, action="auth.login", entity_type="user", entity_id=str(user.id))
    await db.commit()
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=int(ABSOLUTE_TIMEOUT.total_seconds()),
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        role=Role(user.role),
        token=token,
        settings=settings,
    )


@router.post("/logout", status_code=204)
async def logout(principal: PrincipalDep, db: SessionDep, settings: SettingsDep) -> Response:
    await revoke_session(db, principal.session_token, now=utcnow())
    await audit(
        db,
        actor_user_id=principal.user_id,
        action="auth.logout",
        entity_type="user",
        entity_id=str(principal.user_id),
    )
    await db.commit()
    response = Response(status_code=204)
    response.delete_cookie(
        settings.session_cookie_name,
        path="/",
        secure=settings.session_cookie_secure,
        httponly=True,
        samesite="strict",
    )
    return response


@router.get("/session", response_model=SessionResponse)
async def session(principal: PrincipalDep, response: Response, settings: SettingsDep) -> SessionResponse:
    response.headers["Cache-Control"] = "no-store"
    return _session_response(
        user_id=principal.user_id,
        email=principal.email,
        display_name=principal.display_name,
        role=principal.role,
        token=principal.session_token,
        settings=settings,
    )
