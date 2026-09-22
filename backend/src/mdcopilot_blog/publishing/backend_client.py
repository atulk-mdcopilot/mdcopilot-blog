"""Saves a finished draft to MDCopilot Blogs through the backend's internal ingest route."""

import httpx

from mdcopilot_blog.settings import Settings

DRAFTS_PATH = "/internal/v1/blog/drafts"
CONNECT_TIMEOUT_SECONDS = 5.0
ERROR_TEXT_LIMIT = 500


class BackendDraftError(RuntimeError):
    """The backend answered the draft POST with something other than 201."""

    def __init__(self, status_code: int, detail: str) -> None:
        # Keep every constructor argument in ``args`` so the exception pickles (DBOS stores step errors).
        super().__init__(status_code, detail)
        self.status_code = status_code
        self.detail = detail

    def __str__(self) -> str:
        return f"backend refused the draft ({self.status_code}): {self.detail}"


def _error_text(response: httpx.Response) -> str:
    try:
        body = response.json()
        detail = body.get("detail") or body.get("message") or body.get("title") if isinstance(body, dict) else None
    except ValueError:
        detail = None
    return str(detail or response.text)[:ERROR_TEXT_LIMIT]


async def create_draft(
    settings: Settings, *, author_id: str, title: str, content: str, excerpt: str, slug: str | None
) -> tuple[str, str]:
    """POST the draft; return the backend's (blog id, slug). The token and the HTML are never logged."""
    if settings.backend_internal_url is None or settings.backend_internal_token is None:
        raise RuntimeError("BACKEND_INTERNAL_URL and BACKEND_INTERNAL_TOKEN must be set to save drafts")
    payload = {"author_id": author_id, "title": title, "content": content}
    if excerpt:
        payload["excerpt"] = excerpt
    if slug:
        payload["slug"] = slug
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(settings.backend_timeout_seconds, connect=CONNECT_TIMEOUT_SECONDS)
        ) as client:
            response = await client.post(
                settings.backend_internal_url + DRAFTS_PATH,
                json=payload,
                headers={"X-Internal-Token": settings.backend_internal_token.get_secret_value()},
            )
    except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
        # Nothing was sent, so a retry is safe. retry.transient retries the builtin ConnectionError only and
        # httpx errors do not derive from it. A read timeout is not retried: the draft may already exist.
        raise ConnectionError(f"backend unreachable: {type(exc).__name__}") from exc
    if response.status_code != 201:
        raise BackendDraftError(response.status_code, _error_text(response))
    body = response.json()
    return str(body["id"]), str(body["slug"])
