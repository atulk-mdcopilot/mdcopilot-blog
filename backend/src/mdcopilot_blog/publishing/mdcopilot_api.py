"""MDCopilot publisher with exact-slug reconciliation after uncertain creates."""

from datetime import UTC, datetime
from http.cookies import SimpleCookie
from typing import Any
from urllib.parse import quote

import httpx

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import Issue, PublicationResult, PublisherCapabilities, PublishPayload, RemotePost
from mdcopilot_blog.publishing.renderer import validate_payload
from mdcopilot_blog.settings import Settings

FIND_EXISTING_PAGE_SIZE = 50
FIND_EXISTING_MAX_PAGES = 20


class PublisherRequestError(RuntimeError):
    pass


class MDCopilotApiPublisher:
    key = "mdcopilot_api"

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._token: str | None = None

    def capabilities(self) -> PublisherCapabilities:
        return PublisherCapabilities(network=True, supports_update=True, supports_draft=True, seo_fields=False)

    async def validate(self, payload: PublishPayload) -> list[Issue]:
        return validate_payload(payload)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.settings.publisher_api_url.rstrip("/") + "/",
            timeout=self.settings.publisher_timeout_seconds,
            follow_redirects=False,
            headers={
                "Accept": "application/json",
                "User-Agent": f"mdcopilot-blog/{self.settings.app_version} publisher",
            },
        )

    def _credentials(self) -> tuple[str, str]:
        login = self.settings.publisher_login_id
        password = self.settings.publisher_password
        if not login or not password or not password.get_secret_value().strip():
            raise PublisherRequestError(
                "publisher credentials are not configured (BLOG_PUBLISHER_LOGIN_ID and BLOG_PUBLISHER_PASSWORD)"
            )
        return login, password.get_secret_value()

    async def _login(self, client: httpx.AsyncClient) -> None:
        login, password = self._credentials()
        try:
            response = await client.post(
                self.settings.publisher_login_path.lstrip("/"), json={"phone": login, "password": password}
            )
        except httpx.TransportError as exc:
            raise PublisherRequestError(f"login failed: {type(exc).__name__}") from None
        if response.status_code != 200:
            raise PublisherRequestError(f"login failed: HTTP {response.status_code}")
        for value in response.headers.get_list("set-cookie"):
            cookie = SimpleCookie()
            cookie.load(value)
            for name, morsel in cookie.items():
                if name == "access_token" or name.endswith("_access_token"):
                    self._token = morsel.value
                    break
        client.cookies.clear()
        if not self._token:
            raise PublisherRequestError("login succeeded but no access-token cookie was returned")

    async def _request(self, client: httpx.AsyncClient, method: str, path: str, **kwargs: Any) -> httpx.Response:
        if not self._token:
            await self._login(client)
        response = await client.request(
            method, path.lstrip("/"), headers={"Authorization": f"Bearer {self._token}"}, **kwargs
        )
        if response.status_code == 401:
            self._token = None
            await self._login(client)
            response = await client.request(
                method, path.lstrip("/"), headers={"Authorization": f"Bearer {self._token}"}, **kwargs
            )
        return response

    def _remote(self, row: dict[str, Any]) -> RemotePost:
        return RemotePost(
            external_id=str(row["id"]),
            title=str(row["title"]),
            slug=str(row["slug"]),
            status=str(row["status"]),
            url=f"{self.settings.publisher_public_url.rstrip('/')}/blog/{row['slug']}"
            if row["status"] == "published"
            else None,
        )

    async def _find(self, client: httpx.AsyncClient, payload: PublishPayload) -> RemotePost | None:
        response = await client.get("blogs/" + quote(payload.slug, safe=""))
        if response.status_code == 200:
            row = response.json()
            if row.get("slug") == payload.slug:
                return self._remote(row)
        elif response.status_code != 404:
            raise PublisherRequestError(f"MDCopilot returned HTTP {response.status_code} during public lookup")
        for search in (payload.title, None):
            for page in range(FIND_EXISTING_MAX_PAGES):
                params: dict[str, str | int] = {
                    "skip": page * FIND_EXISTING_PAGE_SIZE,
                    "limit": FIND_EXISTING_PAGE_SIZE,
                }
                if search:
                    params["search"] = search
                response = await self._request(client, "GET", "/admin/blogs", params=params)
                if response.status_code != 200:
                    raise PublisherRequestError(f"MDCopilot returned HTTP {response.status_code} during admin lookup")
                rows = response.json()
                if not isinstance(rows, list):
                    raise PublisherRequestError("invalid response during admin lookup")
                for row in rows:
                    if row.get("slug") == payload.slug:
                        return self._remote(row)
                if len(rows) < FIND_EXISTING_PAGE_SIZE:
                    break
        return None

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None:
        self._credentials()
        try:
            async with self._client() as client:
                return await self._find(client, payload)
        except (httpx.TransportError, ValueError, KeyError) as exc:
            raise PublisherRequestError(f"lookup failed: {type(exc).__name__}") from None

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult:
        known_id = payload.external_post_id
        try:
            self._credentials()
            issues = await self.validate(payload)
            if issues:
                raise PublisherRequestError(
                    "validation failed: " + "; ".join(f"{i.field}: {i.message}" for i in issues)
                )
            body = {
                "title": payload.title,
                "slug": payload.slug,
                "content": payload.html,
                "excerpt": payload.excerpt,
                "status": "draft" if as_draft else "published",
            }
            async with self._client() as client:
                response = None
                if known_id:
                    response = await self._request(client, "PUT", "/admin/blogs/" + quote(known_id, safe=""), json=body)
                    if response.status_code == 404:
                        known_id, response = None, None
                if response is None:
                    existing = await self._find(client, payload)
                    if existing is None:
                        try:
                            response = await self._request(client, "POST", "/admin/blogs", json=body)
                        except httpx.TransportError:
                            existing = await self._find(client, payload)
                            if existing is None:
                                raise PublisherRequestError(
                                    "create outcome unknown; no post found during reconciliation"
                                ) from None
                        if response is not None and response.status_code in {400, 409}:
                            existing = await self._find(client, payload)
                    if existing is not None:
                        if existing.slug != payload.slug or existing.title != payload.title:
                            raise PublisherRequestError("slug already belongs to a different post; refusing adoption")
                        known_id = existing.external_id
                        response = await self._request(
                            client, "PUT", "/admin/blogs/" + quote(known_id, safe=""), json=body
                        )
                if response is None or response.status_code not in {200, 201}:
                    raise PublisherRequestError(
                        f"MDCopilot publish failed: HTTP {response.status_code if response else 'unknown'}"
                    )
                row = response.json()
                remote = self._remote(row)
                return PublicationResult(
                    status=PublicationStatus.PUBLISHED,
                    external_id=remote.external_id,
                    published_url=remote.url,
                    published_at=datetime.now(UTC),
                )
        except (PublisherRequestError, httpx.TransportError, ValueError, KeyError) as exc:
            message = str(exc) if isinstance(exc, PublisherRequestError) else f"publisher failed: {type(exc).__name__}"
            return PublicationResult(
                status=PublicationStatus.FAILED,
                external_id=known_id,
                published_url=None,
                published_at=None,
                message=message,
            )
