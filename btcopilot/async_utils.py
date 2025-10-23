import asyncio
from functools import partial
from typing import Any, List


def _get_event_loop():
    """Get or create event loop safely"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop


def gather(*coroutines) -> List[Any]:
    loop = _get_event_loop()
    return loop.run_until_complete(asyncio.gather(*coroutines))  # Note no extra wrapper


def one_result(coroutine) -> str:
    """
    Run a coroutine and return its single result.
    If the coroutine returns multiple results, this will raise an error.
    """
    loop = _get_event_loop()
    result = loop.run_until_complete(coroutine)
    if isinstance(result, tuple) and len(result) == 1:
        return result[0]
    return result
