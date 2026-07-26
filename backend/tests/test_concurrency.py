"""M3 — run_in_pool executes off the event loop."""
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor

from app.core.concurrency import run_in_pool


def test_runs_on_pool_thread():
    pool = ThreadPoolExecutor(max_workers=1)
    main_thread = threading.current_thread().name

    def blocking(a, b):
        return (threading.current_thread().name, a + b)

    async def go():
        return await run_in_pool(pool, blocking, 2, b=3)

    worker_thread, result = asyncio.run(go())
    assert result == 5
    assert worker_thread != main_thread  # ran off the event-loop thread
    pool.shutdown()
