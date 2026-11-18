"""Apply supabase/migrations/*.sql in order (plain Postgres or Supabase)."""

from __future__ import annotations

import asyncio
from pathlib import Path

from hotelpilot.core import db
from hotelpilot.core.logging import log

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "supabase" / "migrations"


async def migrate() -> list[str]:
    applied: list[str] = []
    async with db.tx() as c:
        # serialize concurrent starters (api + worker)
        await db.exec(c, "select pg_advisory_xact_lock(727274)")
        await db.exec(
            c,
            "create table if not exists schema_migrations"
            " (name text primary key, applied_at timestamptz default now())",
        )
        done = {r["name"] for r in await db.all(c, "select name from schema_migrations")}
        for f in sorted(MIGRATIONS_DIR.glob("*.sql")):
            if f.name in done:
                continue
            raw = await c.get_raw_connection()
            await raw.driver_connection.execute(f.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            await db.exec(c, "insert into schema_migrations(name) values (:n)", n=f.name)
            applied.append(f.name)
    if applied:
        log.info("migrations_applied", files=applied)
    return applied


async def reset_schema() -> None:
    """Tests only: drop everything and migrate from scratch."""
    async with db.tx() as c:
        await db.exec(c, "drop schema if exists public cascade")
        await db.exec(c, "create schema public")
    await migrate()


if __name__ == "__main__":
    asyncio.run(migrate())
