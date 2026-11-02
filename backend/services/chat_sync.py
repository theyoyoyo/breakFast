"""
Live chat sync across a user's devices.

Each user's open chat sockets are kept in memory (the app runs as one server process).
After a session's messages change, the user's sockets get
{"type": "session_updated", "session_id": ...} and reload that chat if it is on screen.
Other changes send a small notice with `notify_user` ({"type": "supplements_updated"},
{"type": "shopping_suggestions_updated"}), which the app passes to every panel.
Only the user's own sockets are told; tokens are never streamed to other devices.
"""

from fastapi import WebSocket

# user_id → open chat sockets. A list compared by identity: Starlette sockets are
# Mappings, so they aren't hashable and two of them can compare equal.
_sockets: dict[int, list[WebSocket]] = {}


def register(user_id: int, websocket: WebSocket) -> None:
    """Add an accepted chat socket to its user's list."""
    _sockets.setdefault(user_id, []).append(websocket)


def unregister(user_id: int, websocket: WebSocket) -> None:
    """Remove a closed chat socket, and the user's entry once it has none left."""
    remaining = [ws for ws in _sockets.get(user_id, []) if ws is not websocket]
    if remaining:
        _sockets[user_id] = remaining
    else:
        _sockets.pop(user_id, None)


async def notify_user(user_id: int, notice: dict, exclude: WebSocket | None = None) -> None:
    """Send a small notice to the user's open chat sockets, except `exclude`."""
    for websocket in list(_sockets.get(user_id, [])):
        if websocket is exclude:
            continue
        try:
            await websocket.send_json(notice)
        except Exception:
            # Gone without a clean disconnect yet: forget it
            unregister(user_id, websocket)


async def notify_session_updated(user_id: int, session_id: str, exclude: WebSocket | None = None) -> None:
    """Tell the user's open chat sockets, except `exclude`, that a session's messages changed."""
    await notify_user(user_id, {"type": "session_updated", "session_id": session_id}, exclude)
