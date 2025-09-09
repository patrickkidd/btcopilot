"""
Async utilities for training interface.

Provides helper functions for running async operations in the training
interface. Stand-in implementation that can be extended by parent application.
"""

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
    """
    Run multiple coroutines concurrently and return their results
    
    Args:
        *coroutines: Coroutines to run concurrently
        
    Returns:
        List of results from the coroutines
    """
    loop = _get_event_loop()
    return loop.run_until_complete(asyncio.gather(*coroutines))


def one_result(coroutine) -> str:
    """
    Run a coroutine and return its single result.
    If the coroutine returns multiple results, this will raise an error.
    
    Args:
        coroutine: Coroutine to run
        
    Returns:
        Single result from the coroutine
    """
    loop = _get_event_loop()
    result = loop.run_until_complete(coroutine)
    if isinstance(result, tuple) and len(result) == 1:
        return result[0]
    return result


def run_async(coroutine):
    """
    Simple helper to run an async function in sync context
    
    Args:
        coroutine: Coroutine to run
        
    Returns:
        Result from the coroutine
    """
    loop = _get_event_loop()
    return loop.run_until_complete(coroutine)


def run_in_background(coroutine):
    """
    Run coroutine in background without blocking - stand-in implementation
    
    Args:
        coroutine: Coroutine to run in background
        
    Returns:
        Task object that can be awaited or cancelled
    """
    loop = _get_event_loop()
    return loop.create_task(coroutine)