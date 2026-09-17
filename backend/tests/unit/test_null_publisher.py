"""NullPublisher: validation, idempotent publish, lookup by slug."""

import uuid

from mdcopilot_blog.domain.enums import PublicationStatus
from mdcopilot_blog.publishing.base import BlogPublisher, PublishPayload
from mdcopilot_blog.publishing.null import NullPublisher


def make_payload(**overrides: object) -> PublishPayload:
    data: dict[str, object] = {
        "article_id": uuid.uuid4(),
        "version_id": uuid.uuid4(),
        "title": "Specialist access in 2026",
        "slug": "specialist-access-2026",
        "html": "<p>Body</p>",
        "excerpt": "Short excerpt",
        "status": "published",
    }
    data.update(overrides)
    return PublishPayload.model_validate(data)


def test_capabilities() -> None:
    publisher: BlogPublisher = NullPublisher()
    caps = publisher.capabilities()
    assert publisher.key == "null"
    assert caps.network is False
    assert caps.supports_update is True
    assert caps.supports_draft is True
    assert caps.seo_fields is True


async def test_validate_requires_title_slug_and_html() -> None:
    publisher = NullPublisher()
    assert await publisher.validate(make_payload()) == []
    issues = await publisher.validate(make_payload(title=" ", slug="", html=""))
    assert [issue.field for issue in issues] == ["title", "slug", "html"]


async def test_publish_is_idempotent_per_key() -> None:
    publisher = NullPublisher()
    payload = make_payload()
    key = str(payload.version_id)

    first = await publisher.publish(payload, idempotency_key=key, as_draft=False)
    second = await publisher.publish(payload, idempotency_key=key, as_draft=False)

    assert first.status == PublicationStatus.PUBLISHED
    assert first.external_id == f"null-{key}"
    assert first.published_url is None
    assert second == first
    assert list(publisher.published) == [key]
    assert publisher.published[key] == payload


async def test_different_keys_create_separate_entries() -> None:
    publisher = NullPublisher()
    one = await publisher.publish(make_payload(slug="one"), idempotency_key="k1", as_draft=False)
    two = await publisher.publish(make_payload(slug="two"), idempotency_key="k2", as_draft=True)
    assert one.external_id != two.external_id
    assert sorted(publisher.published) == ["k1", "k2"]


async def test_find_existing_matches_slug() -> None:
    publisher = NullPublisher()
    payload = make_payload(slug="adopt-me")
    assert await publisher.find_existing(payload) is None

    await publisher.publish(payload, idempotency_key="v1", as_draft=True)
    found = await publisher.find_existing(make_payload(slug="adopt-me", title="Renamed"))
    assert found is not None
    assert found.external_id == "null-v1"
    assert found.slug == "adopt-me"
    assert found.status == "draft"
    assert found.url is None
    assert await publisher.find_existing(make_payload(slug="other")) is None
