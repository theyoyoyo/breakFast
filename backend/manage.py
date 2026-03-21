"""
CLI admin tool for break FAST.
Usage:
    python manage.py add-user "Onur" --pin 1234
    python manage.py add-user "Onur" --pin 1234 --admin
    python manage.py list-users
    python manage.py delete-user "Onur"
    python manage.py backup-db
"""

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

import aiosqlite

from config import DATABASE_PATH
from database import init_db
from auth import hash_pin


async def add_user(name: str, pin: str, is_admin: bool = False) -> None:
    await init_db()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO users (name, pin_hash, is_admin) VALUES (?, ?, ?)",
                (name, hash_pin(pin), 1 if is_admin else 0),
            )
            await db.commit()
            role = "admin" if is_admin else "user"
            print(f"✓ {role} '{name}' created.")
        except aiosqlite.IntegrityError:
            print(f"✗ User '{name}' already exists.", file=sys.stderr)
            sys.exit(1)


async def list_users() -> None:
    await init_db()
    async with aiosqlite.connect(DATABASE_PATH) as db:
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
    await init_db()
    async with aiosqlite.connect(DATABASE_PATH) as db:
        # Delete all user data first
        async with db.execute("SELECT id FROM users WHERE name = ?", (name,)) as cur:
            row = await cur.fetchone()
        if not row:
            print(f"✗ User '{name}' not found.", file=sys.stderr)
            sys.exit(1)

        user_id = row[0]
        for table in [
            "ingredient_inventory", "meal_history", "user_preferences",
            "user_habits", "health_rules",
        ]:
            await db.execute(f"DELETE FROM {table} WHERE user_id = ?", (user_id,))

        await db.execute("DELETE FROM users WHERE id = ?", (user_id,))
        await db.commit()
        print(f"✓ User '{name}' and all their data deleted.")


def backup_db() -> None:
    src = Path(DATABASE_PATH)
    if not src.exists():
        print(f"✗ Database not found at {src}", file=sys.stderr)
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dst = src.parent / f"breakFAST_backup_{timestamp}.db"
    shutil.copy2(src, dst)
    print(f"✓ Backup created: {dst}")


def main():
    parser = argparse.ArgumentParser(description="break FAST admin CLI")
    sub = parser.add_subparsers(dest="command")

    # add-user
    add = sub.add_parser("add-user", help="Create a new user")
    add.add_argument("name", help="Username")
    add.add_argument("--pin", required=True, help="Login PIN")
    add.add_argument("--admin", action="store_true", help="Make admin")

    # list-users
    sub.add_parser("list-users", help="List all users")

    # delete-user
    delete = sub.add_parser("delete-user", help="Delete a user and all their data")
    delete.add_argument("name", help="Username to delete")

    # backup-db
    sub.add_parser("backup-db", help="Create a database backup")

    args = parser.parse_args()

    if args.command == "add-user":
        asyncio.run(add_user(args.name, args.pin, args.admin))
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
