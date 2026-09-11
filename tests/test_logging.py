import subprocess
import sys

import pytest


@pytest.mark.parametrize("blocked_stream", ["stdout", "stderr"])
def test_blocked_console_does_not_block_timer_or_file_logging(tmp_path, blocked_stream):
    # Isolate dictConfig and its worker threads from pytest's own logging handlers.
    result = subprocess.run(
        [sys.executable, "-c", _BLOCKED_CONSOLE_SCRIPT, blocked_stream],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stderr


_BLOCKED_CONSOLE_SCRIPT = """
import asyncio
import io
import logging
import sys
import threading
from pathlib import Path
from time import monotonic

from bot.internal.config_dicts import initial_setup

blocked = threading.Event()
release = threading.Event()


class BlockedStream(io.StringIO):
    def write(self, value):
        blocked.set()
        release.wait()
        return super().write(value)


stdout, stderr = sys.stdout, sys.stderr
sys.stdout, sys.stderr = io.StringIO(), io.StringIO()
setattr(sys, sys.argv[1], BlockedStream())
listeners = initial_setup("test_bot")
# A regression must fail instead of hanging the test process indefinitely.
watchdog = threading.Timer(5, release.set)
watchdog.start()


async def scenario():
    logging.error("trigger blocked console")
    deadline = monotonic() + 2
    while not blocked.is_set() and monotonic() < deadline:
        await asyncio.sleep(0.01)
    assert blocked.is_set()

    started = monotonic()
    await asyncio.sleep(0.05)
    logging.info("scheduled task completed")
    assert monotonic() - started < 1

    path = Path("logs/test_bot.log")
    deadline = monotonic() + 2
    while monotonic() < deadline:
        if "scheduled task completed" in path.read_text():
            break
        await asyncio.sleep(0.01)
    assert not release.is_set(), "event loop waited for console to unblock"
    assert "trigger blocked console" in path.read_text()
    assert "scheduled task completed" in path.read_text()


try:
    asyncio.run(scenario())
finally:
    release.set()
    watchdog.cancel()
    watchdog.join()
    for listener in listeners:
        listener.stop()
    logging.shutdown()
    sys.stdout, sys.stderr = stdout, stderr
"""
