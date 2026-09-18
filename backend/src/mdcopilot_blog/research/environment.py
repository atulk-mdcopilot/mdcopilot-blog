"""Research HTTP environment: clients, headers, robots cache, slots."""

import asyncio
import socket
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Final

if TYPE_CHECKING:
    from mdcopilot_blog.services.step_context import StepContext

import httpx

from mdcopilot_blog.domain.tiers import HeaderProfile
from mdcopilot_blog.settings import Settings

Resolver = Callable[[str, int], Awaitable[list[str]]]
DEFAULT_ACCEPT: Final = "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/html;q=0.8, */*;q=0.5"
ROBOTS_TOKEN: Final = "mdcopilot-blog-bot"
BROWSER_LIKE_HEADERS: Mapping[str, str] = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "none",
    "Sec-Fetch-User": "?1",
    "Upgrade-Insecure-Requests": "1",
}


def user_agent(settings: Settings) -> str:
    contact = settings.fetch_contact
    if contact and contact.strip():
        return f"{ROBOTS_TOKEN}/{settings.app_version} (+{settings.site_url}; {contact.strip()})"
    return f"{ROBOTS_TOKEN}/{settings.app_version} (+{settings.site_url})"


def profile_headers(profile: HeaderProfile, settings: Settings) -> dict[str, str]:
    if profile == "browser_like":
        return dict(BROWSER_LIKE_HEADERS)
    return {
        "User-Agent": user_agent(settings),
        "Accept": DEFAULT_ACCEPT,
        "Accept-Encoding": "gzip, deflate",
    }


def build_http_client(settings: Settings) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        http2=True,
        follow_redirects=False,
        timeout=httpx.Timeout(settings.fetch_read_timeout_seconds, connect=settings.fetch_connect_timeout_seconds),
        limits=httpx.Limits(
            max_connections=settings.max_parallel_fetches,
            max_keepalive_connections=settings.max_parallel_fetches,
        ),
    )


async def system_resolver(host: str, port: int) -> list[str]:
    loop = asyncio.get_running_loop()
    result = await loop.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    addresses: list[str] = []
    for family, type_, proto, canonname, sockaddr in result:
        address = sockaddr[0]
        if isinstance(address, str) and address not in addresses:
            addresses.append(address)
    return addresses


class HostLimiter:
    """One semaphore per normalised host, created on first use."""

    def __init__(self, per_host: int) -> None:
        self._per_host = per_host
        self._semaphores: dict[str, asyncio.Semaphore] = {}

    def slot(self, host: str) -> asyncio.Semaphore:
        key = host.lower()
        semaphore = self._semaphores.get(key)
        if semaphore is None:
            semaphore = asyncio.Semaphore(self._per_host)
            self._semaphores[key] = semaphore
        return semaphore


@dataclass(frozen=True)
class RobotsPolicy:
    allow_all: bool
    disallow_all: bool
    body: str


class RobotsCache:
    def __init__(self) -> None:
        self._entries: dict[str, tuple[datetime, RobotsPolicy]] = {}

    def get(self, origin: str, *, now: datetime, ttl: timedelta) -> RobotsPolicy | None:
        entry = self._entries.get(origin)
        if entry is None:
            return None
        stored_at, policy = entry
        if now - stored_at >= ttl:
            return None
        return policy

    def put(self, origin: str, policy: RobotsPolicy, *, now: datetime) -> None:
        self._entries[origin] = (now, policy)


ROBOTS_CACHE = RobotsCache()


@dataclass
class ResearchEnvironment:
    settings: Settings
    client: httpx.AsyncClient
    resolver: Resolver
    robots: RobotsCache
    now: Callable[[], datetime]
    pubmed_min_interval: float
    fetch_slots: asyncio.Semaphore
    host_limiter: HostLimiter


@asynccontextmanager
async def open_environment(sc: "StepContext") -> AsyncIterator[ResearchEnvironment]:
    """Share the robots cache and close the HTTP client at the end of each research step."""
    async with build_http_client(sc.settings) as client:
        yield ResearchEnvironment(
            settings=sc.settings,
            client=client,
            resolver=system_resolver,
            robots=ROBOTS_CACHE,
            now=sc.now,
            pubmed_min_interval=0.1 if sc.settings.ncbi_api_key is not None else 0.34,
            fetch_slots=asyncio.Semaphore(sc.settings.max_parallel_fetches),
            host_limiter=HostLimiter(sc.settings.fetch_per_host_limit),
        )
