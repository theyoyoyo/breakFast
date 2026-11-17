"""
CLI admin tool for break FAST.
Usage:
    python manage.py add-user "Alice"
    python manage.py add-user "Alice" --admin
    python manage.py set-pin "Alice"
    python manage.py list-users
    python manage.py delete-user "Alice"
    python manage.py backup-db

A PIN needs 6-10 digits. Without --pin the CLI asks for it twice without showing it, which keeps
it out of the shell history.

The CLI never migrates the database: after an update, start the server once first.
"""

import argparse
import asyncio
import getpass
import io
import sqlite3
import sys
from contextlib import asynccontextmanager, closing
from datetime import datetime
from pathlib import Path

import aiosqlite

from config import DATABASE_PATH
from database import MigrationsPending, check_schema
from auth import hash_pin, pin_problem


# Every table holding per-user rows, children before parents
USER_TABLES = [
    "supplement_daily_log", "user_supplements", "user_profiles",
    "product_ratings", "favorite_meals", "suggested_meals", "chat_messages",
    "ingredient_inventory", "ingredient_group_memory", "favorite_ingredients",
    "meal_history", "user_preferences", "user_habits", "health_rules",
    "shopping_list", "shopping_suggestions", "user_kitchen_appliances", "weekly_summaries",
    "chat_sessions",
]


def _check_pin(pin: str) -> None:
    problem = pin_problem(pin)
    if problem:
        print(f"Error: {problem}", file=sys.stderr)
        sys.exit(1)


async def _check_schema() -> None:
    """Stop with a message when the database has migration steps pending: only a server
    start runs them (after a backup), so a command never changes the schema under a
    running server."""
    try:
        await check_schema()
    except MigrationsPending as pending:
        print(
            f"Error: {pending} ({DATABASE_PATH}). Start the server once so it updates the database "
            "(stop an older server first), then run this command again.",
            file=sys.stderr,
        )
        sys.exit(1)


@asynccontextmanager
async def _connect():
    """A connection to the database with foreign keys enforced, like the server's."""
    async with aiosqlite.connect(DATABASE_PATH) as db:
        await db.execute("PRAGMA foreign_keys = ON")
        yield db


def _ask_pin() -> str:
    """Ask for a PIN twice without showing it."""
    pin = getpass.getpass("PIN (6-10 digits): ")
    if getpass.getpass("PIN again: ") != pin:
        print("Error: the PINs don't match.", file=sys.stderr)
        sys.exit(1)
    return pin


async def add_user(name: str, pin: str, is_admin: bool = False) -> None:
    _check_pin(pin)
    await _check_schema()
    async with _connect() as db:
        try:
            await db.execute(
                "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
                (name, hash_pin(pin), 1 if is_admin else 0),
            )
            await db.commit()
            role = "admin" if is_admin else "user"
            print(f"{role.capitalize()} '{name}' created.")
        except aiosqlite.IntegrityError:
            print(f"Error: user '{name}' already exists.", file=sys.stderr)
            sys.exit(1)


async def set_pin(name: str, pin: str) -> None:
    """Give a user a new PIN (6-10 digits); their old PIN stops working."""
    _check_pin(pin)
    await _check_schema()
    async with _connect() as db:
        cur = await db.execute("UPDATE users SET pin_hash = ? WHERE name = ?", (hash_pin(pin), name))
        await db.commit()
    if not cur.rowcount:
        print(f"Error: user '{name}' not found.", file=sys.stderr)
        sys.exit(1)
    print(f"PIN changed for '{name}'.")


async def list_users() -> None:
    await _check_schema()
    async with _connect() as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT id, name, is_admin, created_at FROM users ORDER BY id") as cur:
            rows = await cur.fetchall()

    if not rows:
        print("No users found.")
        return

    print(f"{'ID':<5} {'Name':<20} {'Admin':<8} {'Created'}")
    print("-" * 60)
    for r in rows:
        admin = "yes" if r["is_admin"] else "no"
        print(f"{r['id']:<5} {r['name']:<20} {admin:<8} {r['created_at']}")


async def delete_user(name: str) -> None:
    await _check_schema()
    async with _connect() as db:
        # Delete all user data first
        async with db.execute("SELECT id FROM users WHERE name = ?", (name,)) as cur:
            row = await cur.fetchone()
        if not row:
            print(f"Error: user '{name}' not found.", file=sys.stderr)
            sys.exit(1)

        user_id = row[0]
        for table in USER_TABLES:
            await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))

        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        print(f"User '{name}' and all their data deleted.")


def backup_db() -> None:
    """Back up the database to a timestamped file next to it. SQLite's backup API takes a
    consistent snapshot, writes still in the WAL included, so it's safe while the server runs."""
    src = Path(DATABASE_PATH)
    if not src.exists():
        print(f"Error: database not found at {src}", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.parent / f"breakFAST_backup_{timestamp}.db"
    with closing(sqlite3.connect(src)) as source, closing(sqlite3.connect(dst)) as backup:
        source.backup(backup)
        # One self-contained file, so the backup needs no -wal beside it
        backup.execute("PRAGMA journal_mode=DELETE")
        problem = _integrity_problem(backup)
    if problem:
        # A backup that can't be read back is worse than none: say so and don't call it a backup
        dst.unlink()
        print(f"Error: the backup failed its integrity check ({problem}); no backup was kept.", file=sys.stderr)
        sys.exit(1)
    print(f"Backup created: {dst}")


def _integrity_problem(db: sqlite3.Connection) -> str | None:
    """SQLite's own check of a database file: None when it's sound, else the first problem."""
    (result,) = db.execute("PRAGMA integrity_check(1)").fetchone()
    return None if result == "ok" else result


def _safe_output() -> None:
    """Print what the output can't show as '?' instead of crashing: on Windows a pipe or a
    redirect is cp1252, which has no room for a name like 'Ayşe'."""
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(errors="replace")


def main():
    _safe_output()
    parser = argparse.ArgumentParser(description="break FAST admin CLI")
    sub = parser.add_subparsers(dest="command")

    # add-user
    add = sub.add_parser("add-user", help="Create a new user")
    add.add_argument("name", help="Username")
    add.add_argument("--pin", help="Login PIN, 6-10 digits (asked for when left out)")
    add.add_argument("--admin", action="store_true", help="Make admin")

    # set-pin
    set_pin_cmd = sub.add_parser("set-pin", help="Change a user's PIN")
    set_pin_cmd.add_argument("name", help="Username")
    set_pin_cmd.add_argument("--pin", help="New PIN, 6-10 digits (asked for when left out)")

    # list-users
    sub.add_parser("list-users", help="List all users")

    # delete-user
    delete = sub.add_parser("delete-user", help="Delete a user and all their data")
    delete.add_argument("name", help="Username to delete")

    # backup-db
    sub.add_parser("backup-db", help="Create a database backup")

    args = parser.parse_args()

    if args.command == "add-user":
        asyncio.run(add_user(args.name, args.pin or _ask_pin(), args.admin))
    elif args.command == "set-pin":
        asyncio.run(set_pin(args.name, args.pin or _ask_pin()))
    elif args.command == "list-users":
        asyncio.run(list_users())
    elif args.command == "delete-user":
        asyncio.run(delete_user(args.name))
    elif args.command == "backup-db":
        backup_db()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
