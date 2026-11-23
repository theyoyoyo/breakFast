"""
CRUD endpoints for kitchen appliances — per-user appliance ownership config.
On first access, auto-populates all appliances with defaults (stove enabled, rest disabled).
"""

from fastapi import APIRouter, Depends, HTTPException

from auth import require_user
from database import get_db
from models.kitchen import DEFAULT_ENABLED_KEYS, KITCHEN_APPLIANCES, VALID_APPLIANCE_KEYS, KitchenToggle
from models.limits import ApplianceKey

router = APIRouter(prefix="/kitchen", tags=["kitchen"])


async def _ensure_populated(db, user_id: int) -> None:
    """Insert default rows for a user who has no kitchen config yet."""
    async with db.execute(
        "SELECT COUNT(*) FROM user_kitchen_appliances WHERE user_id = ?",
        (user_id,),
    ) as cur:
        count = (await cur.fetchone())[0]
    if count > 0:
        return
    for appliance in KITCHEN_APPLIANCES:
        enabled = 1 if appliance["key"] in DEFAULT_ENABLED_KEYS else 0
        await db.execute(
            "INSERT OR IGNORE INTO user_kitchen_appliances (user_id, appliance_key, enabled) VALUES (?, ?, ?)",
            (user_id, appliance["key"], enabled),
        )
    await db.commit()


@router.get("/")
async def list_kitchen_appliances(user_id: int = Depends(require_user)):
    async with get_db() as db:
        await _ensure_populated(db, user_id)
        rows = await db.execute_fetchall(
            "SELECT appliance_key, enabled FROM user_kitchen_appliances WHERE user_id = ?",
            (user_id,),
        )
        status = {r["appliance_key"]: bool(r["enabled"]) for r in rows}
    return [
        {"key": a["key"], "name": a["name"], "enabled": status.get(a["key"], False)}
        for a in KITCHEN_APPLIANCES
    ]


@router.put("/{appliance_key}")
async def toggle_kitchen_appliance(
    appliance_key: ApplianceKey,
    body: KitchenToggle,
    user_id: int = Depends(require_user),
):
    if appliance_key not in VALID_APPLIANCE_KEYS:
        raise HTTPException(404, "Unknown appliance")
    async with get_db() as db:
        await _ensure_populated(db, user_id)
        await db.execute(
            "UPDATE user_kitchen_appliances SET enabled = ? WHERE user_id = ? AND appliance_key = ?",
            (1 if body.enabled else 0, user_id, appliance_key),
        )
        await db.commit()
    name = next(a["name"] for a in KITCHEN_APPLIANCES if a["key"] == appliance_key)
    return {"key": appliance_key, "name": name, "enabled": body.enabled}
