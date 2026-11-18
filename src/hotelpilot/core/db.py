"""Thin async DB layer: SQLAlchemy 2 Core + asyncpg, plain SQL."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from hotelpilot.core.config import get_settings

_engine: AsyncEngine | None = None


def engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        _engine = create_async_engine(get_settings().database_url, pool_pre_ping=True, pool_size=5)
    return _engine


async def dispose() -> None:
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


@asynccontextmanager
async def tx() -> AsyncIterator[AsyncConnection]:
    async with engine().begin() as conn:
        yield conn


async def all(conn: AsyncConnection, sql: str, **params: Any) -> list[dict[str, Any]]:
    res = await conn.execute(text(sql), params)
    return [dict(r) for r in res.mappings().all()]


async def one(conn: AsyncConnection, sql: str, **params: Any) -> dict[str, Any] | None:
    res = await conn.execute(text(sql), params)
    row = res.mappings().first()
    return dict(row) if row else None


async def val(conn: AsyncConnection, sql: str, **params: Any) -> Any:
    res = await conn.execute(text(sql), params)
    return res.scalar()


async def exec(conn: AsyncConnection, sql: str, **params: Any) -> int:
    res = await conn.execute(text(sql), params)
    return res.rowcount or 0


async def get_setting(conn: AsyncConnection, key: str, default: Any = None) -> Any:
    v = await val(conn, "select value from settings where key = :k", k=key)
    return default if v is None else v


async def set_setting(conn: AsyncConnection, key: str, value: Any) -> None:
    import json

    await exec(
        conn,
        "insert into settings(key, value) values (:k, cast(:v as jsonb)) "
        "on conflict (key) do update set value = excluded.value, updated_at = now()",
        k=key,
        v=json.dumps(value),
    )
