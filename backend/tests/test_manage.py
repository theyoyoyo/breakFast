"""Tests for the admin CLI (manage.py)."""

import asyncio
import io
import sqlite3
import sys
from contextlib import closing
from pathlib import Path

import aiosqlite
import pytest

import database
import manage
from auth import pin_problem, verify_pin


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

    await manage.add_user("alice", "135792")
    await manage.add_user("bob", "246813")
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


async def _pin_hash(db_path: str, name: str) -> str:
    async with aiosqlite.connect(db_path) as db:
        async with db.execute("SELECT pin_hash FROM users WHERE name = ?", (name,)) as cur:
            return (await cur.fetchone())[0]


@pytest.fixture
def cli_db(tmp_path, monkeypatch):
    db_path = str(tmp_path / "test.db")
    monkeypatch.setattr(database, "DATABASE_PATH", db_path)
    monkeypatch.setattr(manage, "DATABASE_PATH", db_path)
    return db_path


# A new or changed PIN needs 6-10 ASCII digits
def test_pin_problem():
    assert pin_problem("135792") is None
    assert pin_problem("1357924680") is None
    for pin in ("", "13579", "13579246801", "abcdef", "13579a", "135 792", "١٢٣٤٥٦"):
        assert pin_problem(pin), pin


# add-user refuses a PIN under 6 digits and creates no user
async def test_add_user_refuses_short_pin(cli_db, capsys):
    await database.init_db()
    with pytest.raises(SystemExit):
        await manage.add_user("alice", "13579")
    assert "6-10 digits" in capsys.readouterr().err
    async with aiosqlite.connect(cli_db) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            assert (await cur.fetchone())[0] == 0


# set-pin gives a user a new PIN: the new one verifies and the old one stops working
async def test_set_pin_changes_pin(cli_db):
    await manage.add_user("alice", "135792")
    await manage.set_pin("alice", "97531864")
    stored = await _pin_hash(cli_db, "alice")
    assert verify_pin("97531864", stored)
    assert not verify_pin("135792", stored)


# set-pin refuses a short PIN and keeps the old one
async def test_set_pin_refuses_short_pin(cli_db):
    await manage.add_user("alice", "135792")
    with pytest.raises(SystemExit):
        await manage.set_pin("alice", "1357")
    assert verify_pin("135792", await _pin_hash(cli_db, "alice"))


# set-pin for a name that doesn't exist exits with an error
async def test_set_pin_unknown_user(cli_db, capsys):
    await database.init_db()
    with pytest.raises(SystemExit):
        await manage.set_pin("nobody", "135792")
    assert "not found" in capsys.readouterr().err


# Without --pin the CLI asks twice and stops when the two answers differ
def test_ask_pin_needs_matching_answers(monkeypatch):
    answers = iter(["135792", "135792"])
    monkeypatch.setattr(manage.getpass, "getpass", lambda prompt: next(answers))
    assert manage._ask_pin() == "135792"

    answers = iter(["135792", "135793"])
    with pytest.raises(SystemExit):
        manage._ask_pin()


# A name Windows' cp1252 pipes can't show prints with "?" instead of crashing, and is stored as typed
def test_cli_output_survives_cp1252(cli_db, monkeypatch):
    out = io.TextIOWrapper(io.BytesIO(), encoding="cp1252", newline="\n")
    monkeypatch.setattr(sys, "stdout", out)
    monkeypatch.setattr(sys, "stderr", io.TextIOWrapper(io.BytesIO(), encoding="cp1252"))
    monkeypatch.setattr(sys, "argv", ["manage.py", "add-user", "Ayşe", "--pin", "135792"])
    manage.main()
    out.flush()
    assert out.buffer.getvalue() == b"User 'Ay?e' created.\n"
    assert verify_pin("135792", asyncio.run(_pin_hash(cli_db, "Ayşe")))


def _backup_path(out: str) -> Path:
    return Path(out.split("Backup created: ")[1].strip())


# A row still in the WAL, with no checkpoint yet, is in the backup (a copy of the .db file missed it)
def test_backup_includes_wal_writes(cli_db, capsys):
    asyncio.run(database.init_db())
    with closing(sqlite3.connect(cli_db)) as live:
        live.execute("PRAGMA wal_autocheckpoint=0")
        live.execute("INSERT INTO users (name, pin_hash) VALUES ('Alice', 'x')")
        live.commit()
        assert Path(cli_db + "-wal").stat().st_size > 0
        manage.backup_db()

    with closing(sqlite3.connect(_backup_path(capsys.readouterr().out))) as db:
        assert db.execute("SELECT name FROM users").fetchall() == [("Alice",)]


# The backup is one self-contained file: it passes an integrity check and needs no -wal beside it
def test_backup_is_self_contained(cli_db, capsys):
    asyncio.run(database.init_db())
    manage.backup_db()

    dst = _backup_path(capsys.readouterr().out)
    with closing(sqlite3.connect(dst)) as db:
        assert db.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert not Path(f"{dst}-wal").exists()


# backup-db without a database exits with an error and writes no backup
def test_backup_missing_database(cli_db, capsys):
    with pytest.raises(SystemExit):
        manage.backup_db()
    assert "database not found" in capsys.readouterr().err
    assert not list(Path(cli_db).parent.glob("breakFAST_backup_*"))
