"""
The group of a new Fridge item (#162).

A new item gets the group the user picked, else the user's own pick for the same
name (`ingredient_group_memory`), else the group of the built-in food list
(`data/ingredient_catalog.json`), else Other. Names match exactly (`same_name`:
case, Turkish letters and plurals only), like the fridge check: "Free-range eggs"
isn't "Eggs", so it goes to Other until the user moves it once.

Memory records every name the user added, with its group, so a planned Fridge
quick-add can list what they had before. Only rows marked `picked` count as the
user's choice, so a pick always beats the list: a group is a pick when the user
chooses it in the add panel or moves an item, never when code chose it.

The list holds about 600 common breakfast and home-kitchen foods, each with its
English and Turkish names; the first name in each language is the food's display
name. A name that could belong to two groups ("Pepper": spice or produce) isn't on it.
"""

import json
from pathlib import Path

from models.ingredient import DEFAULT_GROUP
from services.fridge import name_tokens, same_tokens

CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "ingredient_catalog.json"


def load_catalog(path: Path = CATALOG_PATH) -> dict[str, list[dict]]:
    """The built-in food list: {group: [{"en": [names], "tr": [names]}, ...]}."""
    with open(path, encoding="utf-8") as f:
        return json.load(f)


CATALOG = load_catalog()

# Every name on the list, split once: (tokens, group)
_CATALOG_NAMES = [
    (name_tokens(name), group)
    for group, foods in CATALOG.items()
    for food in foods
    for name in food["en"] + food["tr"]
]


def catalog_group(name: str) -> str | None:
    """The list's group for a name, or None when the list doesn't know it."""
    tokens = name_tokens(name)
    return next((group for names, group in _CATALOG_NAMES if same_tokens(tokens, names)), None)


async def _picks(db, user_id: int) -> list[tuple[int, str, str]]:
    """The user's picks as (id, name, group), newest first."""
    async with db.execute(
        """SELECT id, ingredient_name, group_name FROM ingredient_group_memory
           WHERE user_id = ? AND picked = 1 ORDER BY updated_at DESC, id DESC""",
        (user_id,),
    ) as cur:
        return [tuple(row) for row in await cur.fetchall()]


async def resolve_groups(db, user_id: int, names: list[str]) -> dict[str, str]:
    """The group code gives each name: the user's pick, then the list, then Other."""
    picks = [(picked, group, name_tokens(picked)) for _, picked, group in await _picks(db, user_id)]

    def picked_group(name: str) -> str | None:
        # The exact text first, then the newest pick with the same name
        exact = next((group for picked, group, _ in picks if picked == name), None)
        if exact:
            return exact
        tokens = name_tokens(name)
        return next((group for _, group, picked in picks if same_tokens(tokens, picked)), None)

    return {name: picked_group(name) or catalog_group(name) or DEFAULT_GROUP for name in names}


async def remember(db, user_id: int, name: str, group: str, picked: bool) -> None:
    """Record a name the user added, with its group, and whether the user picked that group.

    A pick replaces the user's earlier picks for the same name, which stay recorded as names.
    A group code chose never overwrites a pick.
    """
    if picked:
        tokens = name_tokens(name)
        stale = [
            (row_id,) for row_id, other, _ in await _picks(db, user_id)
            if other != name and same_tokens(tokens, name_tokens(other))
        ]
        await db.executemany("UPDATE ingredient_group_memory SET picked = 0 WHERE id = ?", stale)
    await db.execute(
        """INSERT INTO ingredient_group_memory (user_id, ingredient_name, group_name, picked)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(user_id, ingredient_name) DO UPDATE SET
               group_name = CASE WHEN excluded.picked = 1 OR picked = 0
                                 THEN excluded.group_name ELSE group_name END,
               picked = MAX(picked, excluded.picked),
               updated_at = datetime('now')""",
        (user_id, name, group, int(picked)),
    )


async def regroup_once(db) -> None:
    """The one-time pass when the list arrived: old memory rows become picks, Other items get the list's group.

    Before the list, every add saved its group to memory, the Other default included,
    so a remembered Other can't be told apart from a pick and stays a plain name; any
    other remembered group was the user's. Fridge items in Other move to the list's
    group when the list knows the name; items in any other group stay where the user
    put them.
    """
    await db.execute(
        "UPDATE ingredient_group_memory SET picked = 1 WHERE group_name != ?", (DEFAULT_GROUP,)
    )
    async with db.execute(
        "SELECT id, name FROM ingredient_inventory WHERE group_name = ?", (DEFAULT_GROUP,)
    ) as cur:
        rows = await cur.fetchall()
    moves = [(group, row_id) for row_id, name in rows if (group := catalog_group(name))]
    await db.executemany(
        "UPDATE ingredient_inventory SET group_name = ?, updated_at = datetime('now') WHERE id = ?",
        moves,
    )
