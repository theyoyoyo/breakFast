"""
/sessions endpoints — chat session management and message persistence.
"""

import uuid
from fastapi import APIRouter, Depends
from fastapi.responses import Response
from database import get_db
from auth import require_user

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("/")
async def create_session(user_id: int = Depends(require_user)):
    """Create a new chat session and return its id."""
    session_id = str(uuid.uuid4())
    async with get_db() as db:
        await db.execute(
            "INSERT INTO chat_sessions (id, user_id) VALUES (?, ?)",
            (session_id, user_id),
        )
        await db.commit()
    return {"session_id": session_id}


@router.get("/")
async def list_sessions(user_id: int = Depends(require_user)):
    """List all sessions for the current user, newest first."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, created_at, updated_at FROM chat_sessions
            WHERE user_id = ? ORDER BY rowid DESC
            """,
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.get("/active")
async def get_active_session(user_id: int = Depends(require_user)):
    """Get the most recent session (or create one if none exists)."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT id, created_at, updated_at FROM chat_sessions
            WHERE user_id = ? ORDER BY rowid DESC LIMIT 1
            """,
            (user_id,),
        ) as cur:
            row = await cur.fetchone()

        if row:
            return dict(row)

        # No session exists — create one
        session_id = str(uuid.uuid4())
        await db.execute(
            "INSERT INTO chat_sessions (id, user_id) VALUES (?, ?)",
            (session_id, user_id),
        )
        await db.commit()
        return {"id": session_id, "created_at": None, "updated_at": None}


@router.delete("/{session_id}")
async def delete_session(session_id: str, user_id: int = Depends(require_user)):
    """Delete a session and its messages. Returns 204."""
    async with get_db() as db:
        await db.execute(
            "DELETE FROM suggested_meals WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        await db.execute(
            "DELETE FROM chat_messages WHERE session_id = ? AND user_id = ?",
            (session_id, user_id),
        )
        await db.execute(
            "DELETE FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        await db.commit()
    return Response(status_code=204)


@router.get("/{session_id}/messages")
async def get_messages(session_id: str, user_id: int = Depends(require_user)):
    """Get all messages for a session."""
    async with get_db() as db:
        async with db.execute(
            """
            SELECT role, content, created_at FROM chat_messages
            WHERE session_id = ? AND user_id = ?
            ORDER BY created_at ASC
            """,
            (session_id, user_id),
        ) as cur:
            rows = await cur.fetchall()
    return [dict(r) for r in rows]


@router.post("/{session_id}/messages")
async def save_message(session_id: str, body: dict, user_id: int = Depends(require_user)):
    """Save a message to a session (used by demo meal injection)."""
    role = body.get("role", "assistant")
    content = body.get("content", "")
    async with get_db() as db:
        await db.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (session_id, user_id, role, content),
        )
        await db.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ?",
            (session_id,),
        )
        await db.commit()
    return {"status": "ok"}
