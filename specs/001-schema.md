# 001 — Schema, migrations, RLS

**Goal**: all tables from ARCHITECTURE §6 (v0.3: no `embedding`, no rating), `pg_trgm`, RLS, seeds.

**Contract**
- Migrations: `supabase/migrations/NNNN_*.sql`, applied in order by `python -m hotelpilot.core.migrate`
  (tracked in `schema_migrations`, advisory-locked so api + worker can start together). The same files work
  with `supabase db reset`.
- Roles `anon`, `authenticated`, `service_role` are created when missing (plain Postgres in docker compose).
- RLS enabled on every table; no policies for anon/authenticated → they read nothing. The agent connects as owner.
- Seeds: `regions` (Bali + 10 sub-areas with bbox `[w,s,e,n]`), `sources` (overture, osm with ToS notes,
  license, attribution, cache TTL), `settings` (kill_switch, review_mode, budget_daily_usd, style_guide, ...).

**Acceptance** (tests/integration/test_schema.py)
- Fresh migrate succeeds; re-running applies nothing.
- `SET ROLE anon` → `count(*)` = 0 on every internal table, even with rows present.

**Additions vs ARCH §6**: `hotel_snapshots.changed_fields`, `description`, `fetched_at`; `raw_snapshots.sweep_id`, `release`;
`sources.license`, `attribution`; `articles.qa_report`, `fact_pack`, `region_id`; `insight_refs.fact_key`;
`topics.title`; `social_posts.lang`, `published_at`, `error`; `jobs.result`, `locked_by`; `run_logs.message`, `llm_billed_tokens`.
