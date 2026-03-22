"""
/health-rules — health rule CRUD endpoints.
All queries are scoped to the authenticated user.
"""

from database import get_db
from fastapi import APIRouter, Depends, HTTPException
from auth import require_user
from pydantic import BaseModel, Field
from typing import Literal


router = APIRouter(prefix="/health-rules", tags=["health-rules"])


class HealthRuleIn(BaseModel):
    rule_text: str
    priority: Literal["low", "high", "critical"] = "high"


class HealthRuleUpdate(BaseModel):
    rule_text: str | None = None
    priority: Literal["low", "high", "critical"] | None = None


class HealthRuleOut(BaseModel):
    id: int
    user_id: int
    rule_text: str
    priority: str
    created_at: str
    updated_at: str


@router.get("/", response_model=list[HealthRuleOut])
async def list_health_rules(user_id: int = Depends(require_user)):
    async with get_db() as db:
        async with db.execute(
            "SELECT * FROM health_rules WHERE user_id = ? ORDER BY id",
            (user_id,),
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]


@router.post("/", response_model=HealthRuleOut, status_code=201)
async def create_health_rule(body: HealthRuleIn, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "INSERT INTO health_rules (user_id, rule_text, priority) VALUES (?, ?, ?)",
            (user_id, body.rule_text, body.priority),
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM health_rules WHERE id = last_insert_rowid()"
        ) as cur:
            return dict(await cur.fetchone())


@router.put("/{rule_id}", response_model=HealthRuleOut)
async def update_health_rule(rule_id: int, body: HealthRuleUpdate, user_id: int = Depends(require_user)):
    async with get_db() as db:
        updates, params = [], []
        if body.rule_text is not None:
            updates.append("rule_text = ?")
            params.append(body.rule_text)
        if body.priority is not None:
            updates.append("priority = ?")
            params.append(body.priority)
        if not updates:
            raise HTTPException(status_code=400, detail="Nothing to update")
        updates.append("updated_at = datetime('now')")
        params.extend([rule_id, user_id])
        await db.execute(
            f"UPDATE health_rules SET {', '.join(updates)} WHERE id = ? AND user_id = ?",
            params,
        )
        await db.commit()
        async with db.execute(
            "SELECT * FROM health_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        ) as cur:
            row = await cur.fetchone()
            if not row:
                raise HTTPException(status_code=404, detail="Rule not found")
            return dict(row)


@router.delete("/{rule_id}", status_code=204)
async def delete_health_rule(rule_id: int, user_id: int = Depends(require_user)):
    async with get_db() as db:
        await db.execute(
            "DELETE FROM health_rules WHERE id = ? AND user_id = ?",
            (rule_id, user_id),
        )
        await db.commit()
