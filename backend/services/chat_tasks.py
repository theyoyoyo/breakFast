"""
One model request per user at a time, across all their devices (#266).

A chat message or a Suggest press runs as an asyncio task the socket can stop. Each user has one
slot, kept in memory like chat_sync's sockets (the app runs as one server process): a request
claims it before its task starts and releases it when the task ends, whether it finished, failed,
was stopped or its device dropped. A request that finds the slot taken gets BUSY_TEXTS instead,
which reaches no model and isn't saved.
"""

import asyncio
from dataclasses import dataclass

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
    task: asyncio.Task | None = None
    # True once the reply is made and being saved: Stop no longer cancels it, so the save is whole
    saving: bool = False


# user_id → the request holding that user's slot
_running: dict[int, Request] = {}


def claim(user_id: int, session_id: str) -> Request | None:
    """Take the user's slot for a new request, or None when one of theirs already runs.
    Synchronous, so two devices can't both take it."""
    if user_id in _running:
        return None
    request = Request(session_id=session_id)
    _running[user_id] = request
    return request


def release(user_id: int, request: Request) -> None:
    """Free the user's slot if this request holds it (safe to call more than once)."""
    if _running.get(user_id) is request:
        del _running[user_id]


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
