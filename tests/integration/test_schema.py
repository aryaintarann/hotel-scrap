"""T-003 acceptance: migrations apply cleanly, seeds exist, anon cannot read internal tables (RLS)."""

from hotelpilot.core import db
from hotelpilot.core.migrate import migrate

INTERNAL = [
    "regions", "sources", "raw_snapshots", "hotels", "hotel_snapshots", "insights", "insight_refs",
    "topics", "articles", "article_i18n", "claim_map", "image_assets", "social_accounts",
    "social_posts", "schedule_slots", "jobs", "run_logs", "settings",
]  # fmt: skip


async def test_migrations_idempotent_and_seeded(conn_db):
    assert await migrate() == []  # second run applies nothing
    async with db.tx() as c:
        assert await db.val(c, "select count(*) from regions where slug = 'bali'") == 1
        assert await db.val(c, "select count(*) from regions") >= 8
        keys = {r["key"] for r in await db.all(c, "select key from sources")}
        assert keys == {"overture", "osm"}
        for k in ("kill_switch", "review_mode", "style_guide", "budget_daily_usd"):
            assert await db.val(c, "select count(*) from settings where key = :k", k=k) == 1
        assert await db.val(c, "select count(*) from pg_extension where extname = 'pg_trgm'") == 1
        cols = {
            r["column_name"]
            for r in await db.all(
                c, "select column_name from information_schema.columns where table_schema='public'"
            )
        }
        assert "embedding" not in cols and "rating" not in cols


async def test_rls_blocks_anon(conn_db):
    async with db.tx() as c:
        await db.exec(c, "insert into jobs(type, payload) values ('x', '{}')")
        for t in INTERNAL:
            assert await db.val(c, f"select relrowsecurity from pg_class where relname = '{t}'"), t
    async with db.tx() as c:
        await db.exec(c, "set local role anon")
        for t in INTERNAL:
            assert await db.val(c, f"select count(*) from {t}") == 0, t
