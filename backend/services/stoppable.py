"""
Stop for the REST calls that wait on the model (#288): shopping suggestions, the weekly analysis and
a meal's nutrition analysis.

The app's Stop aborts the fetch, which closes the HTTP connection, but an aborted request doesn't
cancel a route by itself: the model call would run on and its result be saved for nobody.
`unless_stopped` runs the model call as a task and watches the request's ASGI channel for
`http.disconnect` meanwhile. When the client goes first, the task is cancelled, which closes the
httpx connection to Ollama (as chat's Stop does, services/chat_tasks.py), so Ollama stops too, and
the route ends with RequestStopped: main.py answers it with a bare 499 that nobody reads and the log
gets one info line. Routes save only after the call returns, outside the task, so a stopped call
saves nothing and a save that has begun runs whole.
"""

import asyncio
import logging
from collections.abc import Awaitable
from typing import TypeVar

from fastapi import Request

T = TypeVar("T")

# The status a stopped request is answered with (nginx's "client closed request"); the client is gone
STOPPED_STATUS = 499


class RequestStopped(Exception):
    """The client went away (the app's Stop aborted the fetch) while the model worked."""


async def _disconnected(request: Request) -> None:
    """Return once the client has gone. The route has read its body by now, so the next message on
    the request's channel is the disconnect (a route without a body gets its empty body first)."""
    while True:
        message = await request.receive()
        if message["type"] == "http.disconnect":
            return


async def unless_stopped(request: Request, work: Awaitable[T]) -> T:
    """Await `work` (the model call) and return its result, unless the client disconnects first:
    then cancel it, wait until it has closed its connection, and raise RequestStopped."""
    task = asyncio.ensure_future(work)
    watch = asyncio.ensure_future(_disconnected(request))
    try:
        await asyncio.wait({task, watch}, return_when=asyncio.FIRST_COMPLETED)
        if not task.done() and not watch.cancelled() and watch.exception() is not None:
            # The channel failed without a disconnect: nothing to stop for, so just wait for the call
            logging.debug("Could not watch %s for a disconnect", request.url.path, exc_info=watch.exception())
            await task
    except asyncio.CancelledError:
        task.cancel()
        raise
    finally:
        watch.cancel()

    if task.done():
        return task.result()

    task.cancel()
    await asyncio.gather(task, return_exceptions=True)  # its connection is closed before the route ends
    logging.info("Stopped by the client: %s %s", request.method, request.url.path)
    raise RequestStopped
