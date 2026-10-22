"""Tests for the admin CLI (manage.py)."""

import aiosqlite

import database
import manage


async def _tables_with_user_id(db_path: str) -> set[str]:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT name FROM sqlite_master WHERE type = 'table'") as cur:
            tables = [r[0] for r in await cur.fetchall()]
        found = set()
        for table in tables:
            async with db.execute(f"PRAGMA table_info({table})") as cur:
                if any(col[1] == "user_id" for col in await cur.fetchall()):
                    found.add(table)
        return found


async def test_user_tables_cover_schema(tmp_path, monkeypatch):
    """delete-user must clear every table that has a user_id column."""
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    await database.init_db()

    assert set(manage.USER_TABLES) == await _tables_with_user_id(db_path)


async def test_delete_user_removes_user_data(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    monkeypatch.setattr(manage, "DATABASE_PATH", db_path)

    await manage.add_user("alice", "1234")
    await manage.add_user("bob", "5678")
    async with aiosqlite.connect(db_path) as db:
        for name in ("alice", "bob"):
            await db.execute(
                "INSERT INTO shopping_list (user_id, item_name) SELECT id, 'milk' FROM users WHERE name = ?",
                (name,),
            )
        await db.commit()

    await manage.delete_user("alice")

    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT name FROM users") as cur:
            assert [r[0] for r in await cur.fetchall()] == ["bob"]
        async with db.execute("SELECT COUNT(*) FROM shopping_list") as cur:
            assert (await cur.fetchone())[0] == 1
