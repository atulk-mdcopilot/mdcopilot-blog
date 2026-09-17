"""Worker process helpers."""

import asyncio
from pathlib import Path

from mdcopilot_blog.worker import heartbeat_loop


async def test_heartbeat_loop_touches_file_until_stopped(tmp_path: Path) -> None:
    path = tmp_path / "heartbeat"
    stop = asyncio.Event()
    task = asyncio.create_task(heartbeat_loop(stop, path=path, interval=0.05))
    await asyncio.sleep(0.02)
    assert path.exists()
    first = path.stat().st_mtime_ns
    await asyncio.sleep(0.15)
    assert path.stat().st_mtime_ns > first
    stop.set()
    await asyncio.wait_for(task, timeout=1)
    assert task.done()
