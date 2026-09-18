"""The research retriever: SSRF guard, robots, redirects, bot walls."""

import re
import time
from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

import httpx

from mdcopilot_blog.domain import urls
from mdcopilot_blog.domain.enums import FetchStatus
from mdcopilot_blog.domain.tiers import HeaderProfile
from mdcopilot_blog.research.environment import (
    ResearchEnvironment,
    Resolver,
    RobotsPolicy,
    profile_headers,
    user_agent,
)

REDIRECT_STATUSES: frozenset[int] = frozenset({301, 302, 303, 307, 308})
ROBOTS_MAX_BYTES = 512_000
_BOT_WALL_STATUSES: frozenset[int] = frozenset({401, 403})
_JUST_A_MOMENT_RE = re.compile(rb"<title[^>]*>\s*just a moment", re.IGNORECASE)


class UrlNotAllowed(Exception):
    """The URL is refused by the SSRF guard."""


@dataclass(frozen=True)
class FetchResult:
    url: str
    final_url: str
    status: FetchStatus
    http_status: int | None
    content_type: str | None
    body: bytes
    etag: str | None
    last_modified: str | None
    not_modified: bool
    error: str | None
    elapsed_ms: int


def _result(
    url: str,
    final_url: str,
    status: FetchStatus,
    *,
    http_status: int | None = None,
    content_type: str | None = None,
    body: bytes = b"",
    etag: str | None = None,
    last_modified: str | None = None,
    not_modified: bool = False,
    error: str | None = None,
    started: float = 0.0,
) -> FetchResult:
    return FetchResult(
        url=url,
        final_url=final_url,
        status=status,
        http_status=http_status,
        content_type=content_type,
        body=body,
        etag=etag,
        last_modified=last_modified,
        not_modified=not_modified,
        error=error,
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


def _is_global(address: str) -> bool:
    import ipaddress

    ip = ipaddress.ip_address(address.strip("[]"))
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        ip = ip.ipv4_mapped
    return ip.is_global


async def check_url_allowed(url: str, resolver: Resolver) -> None:
    if not urls.is_http_url(url):
        raise UrlNotAllowed("unsupported URL")
    parts = urlsplit(url)
    if parts.port is not None and parts.port not in (80, 443):
        raise UrlNotAllowed("port not allowed")
    host = parts.hostname or ""
    import ipaddress

    try:
        ipaddress.ip_address(host.strip("[]"))
        if not _is_global(host):
            raise UrlNotAllowed(f"non-public address {host.strip('[]')}")
    except ValueError:
        try:
            addresses = await resolver(host, parts.port or (443 if parts.scheme == "https" else 80))
        except OSError:
            raise UrlNotAllowed("host did not resolve") from None
        if not addresses:
            raise UrlNotAllowed("host did not resolve")
        for address in addresses:
            if not _is_global(address):
                raise UrlNotAllowed(f"non-public address {address.strip('[]')}")


def is_bot_wall(status: int, headers: Mapping[str, str], body: bytes) -> bool:
    if status in _BOT_WALL_STATUSES:
        return True
    if any(key.lower() == "cf-mitigated" and value.lower() == "challenge" for key, value in headers.items()):
        return True
    return _JUST_A_MOMENT_RE.search(body[:65536]) is not None


async def robots_allows(env: ResearchEnvironment, url: str) -> bool:
    parts = urlsplit(url)
    origin = f"{parts.scheme}://{parts.netloc}"
    ttl_value = env.settings.robots_cache_hours
    from datetime import timedelta

    ttl = timedelta(hours=ttl_value)
    cached = env.robots.get(origin, now=env.now(), ttl=ttl)
    if cached is not None:
        if cached.allow_all:
            return True
        if cached.disallow_all:
            return False
        from protego import Protego  # type: ignore[import-untyped, unused-ignore]

        return Protego.parse(cached.body).can_fetch(url, user_agent(env.settings))
    robots_url = origin + "/robots.txt"
    result = await _fetch(env, robots_url, check_robots=False, max_bytes=ROBOTS_MAX_BYTES, slotted=False)
    if result.status == FetchStatus.OK and result.http_status is not None and 200 <= result.http_status < 300:
        body = result.body.decode("utf-8", errors="replace")
        policy = RobotsPolicy(allow_all=False, disallow_all=False, body=body)
    elif result.http_status is not None and 400 <= result.http_status < 500:
        policy = RobotsPolicy(allow_all=True, disallow_all=False, body="")
    else:
        policy = RobotsPolicy(allow_all=False, disallow_all=True, body="")
    env.robots.put(origin, policy, now=env.now())
    if policy.allow_all:
        return True
    if policy.disallow_all:
        return False
    from protego import Protego  # type: ignore[import-untyped, unused-ignore]

    return Protego.parse(policy.body).can_fetch(url, user_agent(env.settings))


async def fetch(
    env: ResearchEnvironment,
    url: str,
    *,
    header_profile: HeaderProfile = "default",
    etag: str | None = None,
    last_modified: str | None = None,
    check_robots: bool = True,
    max_bytes: int | None = None,
) -> FetchResult:
    async with env.fetch_slots:
        return await _fetch(
            env,
            url,
            header_profile=header_profile,
            etag=etag,
            last_modified=last_modified,
            check_robots=check_robots,
            max_bytes=max_bytes,
            slotted=True,
        )


async def _fetch(
    env: ResearchEnvironment,
    url: str,
    *,
    header_profile: HeaderProfile = "default",
    etag: str | None = None,
    last_modified: str | None = None,
    check_robots: bool = True,
    max_bytes: int | None = None,
    slotted: bool = True,
) -> FetchResult:
    started = time.perf_counter()
    current = url
    cap = max_bytes if max_bytes is not None else env.settings.fetch_max_bytes
    for _hop in range(env.settings.fetch_max_redirects + 1):
        try:
            await check_url_allowed(current, env.resolver)
        except UrlNotAllowed as exc:
            return _result(url, current, FetchStatus.ERROR, error=f"url not allowed: {exc}", started=started)
        if check_robots and not await robots_allows(env, current):
            return _result(
                url, current, FetchStatus.ROBOTS_DISALLOWED, error="robots.txt disallows this URL", started=started
            )
        headers = profile_headers(header_profile, env.settings)
        if _hop == 0:
            if etag:
                headers["If-None-Match"] = etag
            if last_modified:
                headers["If-Modified-Since"] = last_modified
        host = urlsplit(current).hostname or ""
        try:
            async with env.host_limiter.slot(host), env.client.stream("GET", current, headers=headers) as response:
                status = response.status_code
                if status in REDIRECT_STATUSES and "location" in response.headers:
                    location = response.headers["location"]
                    current = str(response.url.join(location))
                    continue
                if status == 304:
                    return _result(
                        url,
                        str(response.url),
                        FetchStatus.OK,
                        http_status=304,
                        not_modified=True,
                        etag=etag,
                        last_modified=last_modified,
                        started=started,
                    )
                body = bytearray()
                exceeded = False
                async for chunk in response.aiter_bytes():
                    body += chunk
                    if len(body) > cap:
                        exceeded = True
                        break
                if exceeded:
                    return _result(
                        url,
                        current,
                        FetchStatus.ERROR,
                        http_status=status,
                        error=f"body exceeds {cap} bytes",
                        started=started,
                    )
                content = bytes(body)
                if is_bot_wall(status, dict(response.headers), content):
                    return _result(
                        url,
                        str(response.url),
                        FetchStatus.BLOCKED,
                        http_status=status,
                        body=content,
                        error="bot wall",
                        started=started,
                    )
                if status >= 400:
                    return _result(
                        url,
                        str(response.url),
                        FetchStatus.ERROR,
                        http_status=status,
                        body=content,
                        error=f"HTTP {status}",
                        started=started,
                    )
                if 200 <= status < 300:
                    return _result(
                        url,
                        str(response.url),
                        FetchStatus.OK,
                        http_status=status,
                        content_type=response.headers.get("content-type"),
                        body=content,
                        etag=response.headers.get("etag"),
                        last_modified=response.headers.get("last-modified"),
                        started=started,
                    )
                return _result(
                    url,
                    str(response.url),
                    FetchStatus.ERROR,
                    http_status=status,
                    body=content,
                    error=f"HTTP {status}",
                    started=started,
                )
        except httpx.TimeoutException:
            return _result(url, current, FetchStatus.ERROR, error="timeout", started=started)
        except httpx.HTTPError as exc:
            return _result(url, current, FetchStatus.ERROR, error=type(exc).__name__, started=started)
    return _result(url, current, FetchStatus.ERROR, error="too many redirects", started=started)
