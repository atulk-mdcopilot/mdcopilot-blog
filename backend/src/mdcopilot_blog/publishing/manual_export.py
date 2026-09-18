"""Offline publishing; the export is confirmed by a human."""

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import Issue, PublicationResult, PublisherCapabilities, PublishPayload, RemotePost
from mdcopilot_blog.publishing.renderer import validate_payload


class ManualExportPublisher:
    key = "manual_export"

    def capabilities(self) -> PublisherCapabilities:
        return PublisherCapabilities(network=False, supports_update=False, supports_draft=False, seo_fields=True)

    async def validate(self, payload: PublishPayload) -> list[Issue]:
        return validate_payload(payload)

    async def publish(self, payload: PublishPayload, *, idempotency_key: str, as_draft: bool) -> PublicationResult:
        issues = await self.validate(payload)
        return PublicationResult(
            status=PublicationStatus.FAILED if issues else PublicationStatus.EXPORTED,
            external_id=None,
            published_url=None,
            published_at=None,
            message="validation failed: " + "; ".join(f"{i.field}: {i.message}" for i in issues)
            if issues
            else "export bundle ready",
        )

    async def find_existing(self, payload: PublishPayload) -> RemotePost | None:
        return None
