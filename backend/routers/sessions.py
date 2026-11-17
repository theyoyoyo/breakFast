"""
/sessions endpoints — chat session management and message persistence.
Saving or editing a message tells the user's open chat sockets (services/chat_sync).
A meal card's message also keeps the card's "Today I ate" version (`ate_draft`), saved
with that panel's Save button, and each session remembers its selected meal card
(`selected_message_id`), so every device shows the same one.
"""

import json
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Path
from fastapi.responses import Response
from pydantic import BaseModel, StrictInt
from database import get_db
from db_helpers import parse_json_field
from auth import require_user
from services import chat_sync
from models.limits import SESSION_ID_MAX, MessageContent, SizedDict

router = APIRouter(prefix="/sessions", tags=["sessions"])


class MessageIn(BaseModel):
    role: Literal["user", "assistant"] = "assistant"
    content: MessageContent = ""
    select: bool = False  # also make it the selected meal card


class MessageUpdate(BaseModel):
    """Only the fields sent change."""
    content: MessageContent | None = None
    ate_draft: SizedDict | None = None  # a meal object, or null to clear it


class SelectedIn(BaseModel):
    message_id: StrictInt | None = None  # a number; null selects none


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
    """Get all messages for a session. The id lets a meal card edit update its message;
    `ate_draft` is the card's saved "Today I ate" version, or null; `selected` marks the
    meal card selected for today."""
    async with get_db() as db:
        async with db.execute(
            "SELECT selected_message_id FROM chat_sessions WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        ) as cur:
            session = await cur.fetchone()
        selected_id = session["selected_message_id"] if session else None
        async with db.execute(
            """
            SELECT id, role, content, ate_draft, created_at FROM chat_messages
            WHERE session_id = ? AND user_id = ?
            ORDER BY created_at ASC, id ASC
            """,
            (session_id, user_id),
        ) as cur:
            rows = await cur.fetchall()
    return [
        {**dict(r), "ate_draft": parse_json_field(r["ate_draft"], default=None), "selected": r["id"] == selected_id}
        for r in rows
    ]


@router.post("/{session_id}/messages")
async def save_message(
    body: MessageIn,
    session_id: str = Path(max_length=SESSION_ID_MAX),
    user_id: int = Depends(require_user),
):
    """Save a message to a session (meals sent to chat, analysis and prep plan results).
    `select: true` also makes it the selected meal card (a meal sent to chat)."""
    async with get_db() as db:
        cur = await db.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES (?, ?, ?, ?)",
            (session_id, user_id, body.role, body.content),
        )
        await db.execute(
            "UPDATE chat_sessions SET updated_at = datetime('now') WHERE id = ? AND user_id = ?",
            (session_id, user_id),
        )
        if body.select:
            await db.execute(
                "UPDATE chat_sessions SET selected_message_id = ? WHERE id = ? AND user_id = ?",
                (cur.lastrowid, session_id, user_id),
            )
        await db.commit()
    await chat_sync.notify_session_updated(user_id, session_id)
    return {"status": "ok", "id": cur.lastrowid}


@router.put("/{session_id}/messages/{message_id}")
async def update_message(session_id: str, message_id: int, body: MessageUpdate, user_id: int = Depends(require_user)):
    """Change a message: `content` replaces its text (a meal card edit rewrites the message's
    meal block), `ate_draft` stores the card's "Today I ate" version (null clears it).
    Only the fields sent change; the last save wins."""
    updates = {}
    if "content" in body.model_fields_set:
        updates["content"] = body.content or ""
    if "ate_draft" in body.model_fields_set:
        draft = body.ate_draft
        updates["ate_draft"] = json.dumps(draft, ensure_ascii=False) if draft is not None else None
    if not updates:
        raise HTTPException(status_code=422, detail="Nothing to update")
    set_clause = ", ".join(f"{column} = ?" for column in updates)
    async with get_db() as db:
        cur = await db.execute(
            f"UPDATE chat_messages SET {set_clause} WHERE id = ? AND session_id = ? AND user_id = ?",
            (*updates.values(), message_id, session_id, user_id),
        )
        await db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    await chat_sync.notify_session_updated(user_id, session_id)
    return {"status": "ok"}


@router.put("/{session_id}/selected")
async def select_message(session_id: str, body: SelectedIn, user_id: int = Depends(require_user)):
    """Select a meal card for today (`message_id`), or none (null). The user's devices follow."""
    message_id = body.message_id
    async with get_db() as db:
        if message_id is not None:
            async with db.execute(
                "SELECT 1 FROM chat_messages WHERE id = ? AND session_id = ? AND user_id = ?",
                (message_id, session_id, user_id),
            ) as cur:
                if not await cur.fetchone():
                    raise HTTPException(status_code=404, detail="Message not found")
        cur = await db.execute(
            "UPDATE chat_sessions SET selected_message_id = ? WHERE id = ? AND user_id = ?",
            (message_id, session_id, user_id),
        )
        await db.commit()
    if cur.rowcount == 0:
        raise HTTPException(status_code=404, detail="Session not found")
    await chat_sync.notify_session_updated(user_id, session_id)
    return {"status": "ok"}
