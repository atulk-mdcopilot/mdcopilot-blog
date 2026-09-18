"""Publisher selection and the environment-level network switch."""

import uuid
from urllib.parse import urlsplit

from mdcopilot_blog.domain.config import EffectiveConfig
from mdcopilot_blog.domain.errors import PublishingDisabled
from mdcopilot_blog.publishing.base import BlogPublisher
from mdcopilot_blog.publishing.manual_export import ManualExportPublisher
from mdcopilot_blog.publishing.mdcopilot_api import MDCopilotApiPublisher
from mdcopilot_blog.settings import Settings


def build_publisher(settings: Settings, key: str) -> BlogPublisher:
    if key == "manual_export":
        return ManualExportPublisher()
    if key == "mdcopilot_api":
        return MDCopilotApiPublisher(settings)
    raise ValueError(f"unknown publisher {key}")


def network_publishing_active(settings: Settings, config: EffectiveConfig) -> bool:
    return settings.publishing_enabled and build_publisher(settings, config.publisher).capabilities().network


def ensure_network_publishing(settings: Settings, config: EffectiveConfig) -> None:
    if not settings.publishing_enabled:
        raise PublishingDisabled("BLOG_PUBLISHING_ENABLED is false")
    if not build_publisher(settings, config.publisher).capabilities().network:
        raise PublishingDisabled(
            f"the active publisher {config.publisher} does not publish over the network; use export"
        )


def publisher_target(settings: Settings, key: str) -> str:
    if key == "manual_export":
        return "manual"
    url = urlsplit(settings.publisher_api_url)
    return f"{url.scheme}://{url.netloc}".rstrip("/")


def idempotency_key(key: str, version_id: uuid.UUID) -> str:
    return f"{key}:{version_id}"
