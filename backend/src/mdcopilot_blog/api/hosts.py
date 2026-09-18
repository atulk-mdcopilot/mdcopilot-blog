"""Explicit Host header allow-list, including the configured public origin."""

from urllib.parse import urlsplit

from mdcopilot_blog.settings import Settings

BASE_ALLOWED_HOSTS = ("localhost", "127.0.0.1", "api", "web")


def allowed_hosts(settings: Settings) -> list[str]:
    hosts = list(BASE_ALLOWED_HOSTS)
    host = urlsplit(settings.public_app_url).hostname
    if host and host.lower() not in hosts:
        hosts.append(host.lower())
    return hosts
