"""In-memory publisher for mock mode and tests: records payloads, never touches the network."""

from datetime import UTC, datetime

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import (
    BlogPublisher,
    Issue,
    PublicationResult,
    PublisherCapabilities,
    PublishPayload,
    RemotePost,
)


class NullPublisher(BlogPublisher):
    key = "null"

    def __init__(self) -> None:
        self.published: dict[str, PublishPayload] = {}
        self._results: dict[str, PublicationResult] = {}
        self._drafts: set[str] = set()

    def capabilities(self) -> PublisherCapabilities:
        return PublisherCapabilities(network=False, supports_update=True, supports_draft=True, seo_fields=True)

    async def validate(self, payload: PublishPayload) -> list[Issue]:
        issues: list[Issue] = []
        for field_name in ("title", "slug", "html"):
            if not getattr(payload, field_name).strip():
                issues.append(Issue(field=field_name, message=f"{field_name} must not be empty"))
        return issues

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult:
        existing = self._results.get(idempotency_key)
        if existing is not None:
            return existing
        self.published[idempotency_key] = payload
        if as_draft:
            self._drafts.add(idempotency_key)
        result = PublicationResult(
            status=PublicationStatus.PUBLISHED,
            external_id=f"null-{idempotency_key}",
            published_url=None,
            published_at=datetime.now(UTC),
            message="recorded by NullPublisher (draft)" if as_draft else "recorded by NullPublisher",
        )
        self._results[idempotency_key] = result
        return result

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None:
        for key, stored in self.published.items():
            if stored.slug == payload.slug:
                return RemotePost(
                    external_id=f"null-{key}",
                    slug=stored.slug,
                    status="draft" if key in self._drafts else "published",
                    url=None,
                )
        return None
