import importlib.util

import httpx
import httpx2


def test_h2_is_installed() -> None:
    assert importlib.util.find_spec("h2") is not None


async def test_httpx_async_client_accepts_http2() -> None:
    client = httpx.AsyncClient(http2=True)
    await client.aclose()


async def test_httpx2_async_client_accepts_http2() -> None:
    client = httpx2.AsyncClient(http2=True)
    await client.aclose()
