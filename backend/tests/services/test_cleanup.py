"""
Tests for 48-hour chat session cleanup during init_db.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

import aiosqlite
import pytest

import database
from auth import hash_pin


@pytest.mark.asyncio
async def test_cleanup_removes_old_sessions(tmp_path, monkeypatch):
    """Sessions older than 48h should be deleted on init_db."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)

    # First init to create schema
    await database.init_db()

    # Insert an old session and message (72 hours ago)
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            ("cleanupuser", hash_pin("1234")),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = 'cleanupuser'") as cur:
            user_id = (await cur.fetchone())[0]

        old_time = "datetime('now', '-72 hours')"
        await db.execute(
            f"INSERT INTO chat_sessions (id, user_id, created_at, updated_at) VALUES ('old-session', ?, {old_time}, {old_time})",
            (user_id,),
        )
        await db.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES ('old-session', ?, 'user', 'old message')",
            (user_id,),
        )

        # Insert a recent session (should survive)
        await db.execute(
            "INSERT INTO chat_sessions (id, user_id) VALUES ('new-session', ?)",
            (user_id,),
        )
        await db.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES ('new-session', ?, 'user', 'recent message')",
            (user_id,),
        )
        await db.commit()

    # Re-run init_db which triggers cleanup
    await database.init_db()

    # Verify old session + messages are gone, new ones remain
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT id FROM chat_sessions") as cur:
            sessions = [r[0] for r in await cur.fetchall()]
        async with db.execute("SELECT content FROM chat_messages") as cur:
            messages = [r[0] for r in await cur.fetchall()]

    assert "old-session" not in sessions
    assert "new-session" in sessions
    assert "old message" not in messages
    assert "recent message" in messages


@pytest.mark.asyncio
async def test_cleanup_preserves_recent_sessions(tmp_path, monkeypatch):
    """Sessions younger than 48h should NOT be deleted."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)

    await database.init_db()

    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "INSERT INTO users (name, pin_hash) VALUES (?, ?)",
            ("keepuser", hash_pin("0000")),
        )
        await db.commit()
        async with db.execute("SELECT id FROM users WHERE name = 'keepuser'") as cur:
            user_id = (await cur.fetchone())[0]

        # 24 hours ago — within the 48h window
        recent_time = "datetime('now', '-24 hours')"
        await db.execute(
            f"INSERT INTO chat_sessions (id, user_id, created_at, updated_at) VALUES ('recent-sess', ?, {recent_time}, {recent_time})",
            (user_id,),
        )
        await db.execute(
            "INSERT INTO chat_messages (session_id, user_id, role, content) VALUES ('recent-sess', ?, 'user', 'keep this')",
            (user_id,),
        )
        await db.commit()

    await database.init_db()

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT id FROM chat_sessions WHERE id = 'recent-sess'") as cur:
            row = await cur.fetchone()

    assert row is not None
