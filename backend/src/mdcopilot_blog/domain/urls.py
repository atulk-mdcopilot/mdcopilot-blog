"""URL canonicalisation and registrable domains."""

import hashlib
from urllib.parse import parse_qsl, urlencode, urlsplit

TRACKING_PARAMS: frozenset[str] = frozenset(
    {"fbclid", "gclid", "dclid", "msclkid", "mc_cid", "mc_eid", "_ga", "_gl", "igshid", "rss", "cmpid", "ncid", "ito"}
)
TRACKING_PREFIXES: tuple[str, ...] = ("utm_",)
MULTI_LABEL_SUFFIXES: frozenset[str] = frozenset(
    {
        "co.uk",
        "org.uk",
        "ac.uk",
        "gov.uk",
        "nhs.uk",
        "com.au",
        "org.au",
        "gov.au",
        "co.in",
        "gov.in",
        "co.jp",
        "com.br",
    }
)


class InvalidUrl(ValueError):
    """The value is not a usable http(s) URL."""


def is_http_url(url: str) -> bool:
    parts = urlsplit(url.strip())
    if parts.scheme.lower() not in ("http", "https"):
        return False
    if not parts.hostname:
        return False
    return parts.username is None and parts.password is None


def normalize_host(host: str) -> str:
    host = host.lower().strip()
    host = host.removesuffix(".")
    host = host.removeprefix("www.")
    return host


def host_of(url: str) -> str:
    if not is_http_url(url):
        raise InvalidUrl(f"not an http(s) URL: {url!r}")
    return normalize_host(urlsplit(url.strip()).hostname or "")


def canonicalize_url(url: str) -> str:
    if not is_http_url(url):
        raise InvalidUrl(f"not an http(s) URL: {url!r}")
    parts = urlsplit(url.strip())
    host = normalize_host(parts.hostname or "")
    netloc = host
    if parts.port is not None and parts.port not in (80, 443):
        netloc = f"{host}:{parts.port}"
    path = parts.path or "/"
    if len(path) > 1 and path.endswith("/"):
        path = path.rstrip("/")
    pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_PARAMS and not key.lower().startswith(TRACKING_PREFIXES)
    ]
    pairs.sort()
    query = urlencode(pairs)
    return f"https://{netloc}{path}" + (f"?{query}" if query else "")


def url_hash(canonical_url: str) -> str:
    return hashlib.sha256(canonical_url.encode("utf-8")).hexdigest()


def registrable_domain(host: str) -> str:
    host = normalize_host(host)
    first = host.split(".")[0]
    if first.isdigit() and host.replace(".", "").isdigit():
        return host
    import ipaddress

    try:
        ipaddress.ip_address(host.strip("[]"))
        return host
    except ValueError:
        pass
    labels = host.split(".")
    if len(labels) <= 2:
        return host
    if ".".join(labels[-2:]) in MULTI_LABEL_SUFFIXES:
        return ".".join(labels[-3:])
    return ".".join(labels[-2:])


def domain_suffixes(host: str) -> list[str]:
    host = normalize_host(host)
    labels = host.split(".")
    suffixes = [".".join(labels[i:]) for i in range(len(labels) - 1)]
    return suffixes
