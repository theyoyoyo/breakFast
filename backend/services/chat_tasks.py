"""
One model request per user at a time, across all their devices (#266).

A chat message or a Suggest press runs as an asyncio task the socket can stop. Each user has one
slot, kept in memory like chat_sync's sockets (the app runs as one server process): a request
claims it before its task starts and releases it when the task ends, whether it finished, failed,
was stopped or its device dropped. A request that finds the slot taken gets BUSY_TEXTS instead,
which reaches no model and isn't saved: the device shows it as a short notice, and every socket
that got one is told {"type": "request_ended"} once the running request ends (#283).

The slot is freed by the task's done callback (`start`), not by code inside the task: a Stop that
comes right after its request (a phone's tap sends the click to the Stop button that replaced
Suggest) cancels the task before it has run, and a coroutine cancelled then never runs its own
`finally`.
"""

import asyncio
import logging
from dataclasses import dataclass, field

from fastapi import WebSocket

# The reply to a message or Suggest press sent while the user's last request still runs
# (on this device or another one); nothing is saved or sent to the model
BUSY_TEXTS = {
    "en": "I'm still working on your last request. Please wait for it to finish, or stop it first.",
    "tr": "Son isteğin üzerinde hâlâ çalışıyorum. Lütfen bitmesini bekle ya da önce durdur.",
}


@dataclass(eq=False)
class Request:
    """A user's request in its slot: the chat it answers and the task making the reply."""

    session_id: str
    # The socket that sent it: told when another of the user's devices stops it
    websocket: WebSocket | None = None
    task: asyncio.Task | None = None
    # True once the reply is made and being saved: Stop no longer cancels it, so the save is whole
    saving: bool = False
    # Sockets that got the busy note while this request ran: told when it ends
    watchers: list[WebSocket] = field(default_factory=list)


# user_id → the request holding that user's slot
_running: dict[int, Request] = {}


def claim(user_id: int, session_id: str, websocket: WebSocket | None = None) -> Request | None:
    """Take the user's slot for a new request, or None when one of theirs already runs.
    Synchronous, so two devices can't both take it."""
    if user_id in _running:
        return None
    request = Request(session_id=session_id, websocket=websocket)
    _running[user_id] = request
    return request


def start(user_id: int, request: Request, work) -> asyncio.Task:
    """Run the request's work (a coroutine) as its task. However the task ends (finished, failed,
    or stopped, even before it began), its slot is freed and its watchers are told."""
    task = asyncio.create_task(work)
    request.task = task
    task.add_done_callback(lambda _task: ended(user_id, request))
    return task


# The request_ended sends on their way (kept so they aren't garbage-collected mid-send)
_telling: set[asyncio.Task] = set()


def ended(user_id: int, request: Request) -> None:
    """The request is over: free its slot and tell its watchers. Called by its task's done callback,
    and directly for a request whose task never started."""
    release(user_id, request)
    for websocket in request.watchers:
        sending = asyncio.ensure_future(_tell_ended(websocket))
        _telling.add(sending)
        sending.add_done_callback(_telling.discard)
    request.watchers = []


async def _tell_ended(websocket: WebSocket) -> None:
    try:
        await websocket.send_json({"type": "request_ended"})
    except Exception:
        # Gone already: its device lost the notice with the socket
        logging.debug("A busy device's socket closed before its request ended")


def watch(user_id: int, websocket: WebSocket) -> bool:
    """Tell this socket when the user's running request ends (it got the busy note). False when no
    request runs any more, so there is nothing to wait for."""
    request = _running.get(user_id)
    if request is None:
        return False
    if not any(ws is websocket for ws in request.watchers):
        request.watchers.append(websocket)
    return True


def release(user_id: int, request: Request) -> None:
    """Free the user's slot if this request holds it (safe to call more than once)."""
    if _running.get(user_id) is request:
        del _running[user_id]


def running(user_id: int) -> Request | None:
    """The request holding the user's slot, sent from any of their devices, or None."""
    return _running.get(user_id)


def is_busy(user_id: int) -> bool:
    """True while one of the user's requests holds their slot."""
    return user_id in _running


async def stop(request: Request) -> bool:
    """Stop a request and wait until its task has ended. Returns True when it was cancelled, False
    when it had already ended or was saving its finished reply (the save completes)."""
    task = request.task
    if task is None or task.done():
        return False
    cancelled = not request.saving
    if cancelled:
        task.cancel()
    # asyncio.wait doesn't raise the task's CancelledError into the caller
    await asyncio.wait({task})
    return cancelled
