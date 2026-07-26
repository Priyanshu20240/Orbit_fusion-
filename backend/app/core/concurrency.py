"""Async concurrency helpers.

`run_in_pool` offloads a blocking callable (e.g. a synchronous Earth Engine or
STAC call) onto a threadpool so it does not stall the event loop. The app owns
one such pool on ``app.state.ee_pool`` (created in the lifespan).

Lives at ``app/core/concurrency.py`` since the M6 package move.
"""
from __future__ import annotations

import asyncio
import functools
from concurrent.futures import Executor
from typing import Any, Callable


async def run_in_pool(pool: Executor, fn: Callable[..., Any], *args, **kwargs) -> Any:
    """Await `fn(*args, **kwargs)` on `pool`, off the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(pool, functools.partial(fn, *args, **kwargs))
