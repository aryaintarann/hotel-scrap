-- 0001_init: HotelPilot schema (ARCHITECTURE §6, v0.3: no embedding column, no rating).
-- Works on Supabase and on plain Postgres (roles are created when missing).

create extension if not exists pg_trgm;
create extension if not exists pgcrypto;

do $$
begin
  if not exists (select 1 from pg_roles where rolname = 'anon') then create role anon nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'authenticated') then create role authenticated nologin; end if;
  if not exists (select 1 from pg_roles where rolname = 'service_role') then create role service_role nologin bypassrls; end if;
end $$;

create or replace function touch_updated_at() returns trigger language plpgsql as $$
begin new.updated_at = now(); return new; end $$;

create table regions (
  id uuid primary key default gen_random_uuid(),
  slug text not null unique,
  name text not null,
  parent_slug text,
  bbox double precision[] not null,  -- [west, south, east, north]
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table sources (
  id uuid primary key default gen_random_uuid(),
  key text not null unique,
  config jsonb not null default '{}',
  tos_notes text not null,
  license text not null,
  attribution text not null,
  cache_ttl_days int not null,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table raw_snapshots (
  id uuid primary key default gen_random_uuid(),
  source_id uuid not null references sources(id),
  region_id uuid not null references regions(id),
  external_id text not null,
  payload jsonb not null,
  release text,
  sweep_id text not null,
  fetched_at timestamptz not null,
  expires_at timestamptz not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index raw_snapshots_source_ext on raw_snapshots(source_id, external_id, fetched_at desc);

create table hotels (
  id uuid primary key default gen_random_uuid(),
  canonical_name text not null,
  slug text not null,
  lat double precision not null,
  lng double precision not null,
  address text,
  region_id uuid not null references regions(id),
  star numeric(2,1),
  category text,
  merged_from jsonb not null default '[]',  -- ["osm:node/1", "overture:abc"]
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (region_id, slug)
);
create index hotels_merged_from on hotels using gin (merged_from);

create table hotel_snapshots (
  id uuid primary key default gen_random_uuid(),
  hotel_id uuid not null references hotels(id) on delete cascade,
  source_id uuid not null references sources(id),
  external_id text not null,
  stars numeric(2,1),
  amenities text[] not null default '{}',
  website text,
  phone text,
  email text,
  confidence double precision,
  operating_status text,
  description text,
  attr_hash text not null,
  changed_fields text[] not null default '{}',
  fetched_at timestamptz not null,
  taken_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index hotel_snapshots_hotel on hotel_snapshots(hotel_id, source_id, taken_at desc);

create table insights (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  scope text not null,
  params jsonb not null default '{}',
  result jsonb not null,
  computed_at timestamptz not null default now(),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table insight_refs (
  id uuid primary key default gen_random_uuid(),
  insight_id uuid not null references insights(id) on delete cascade,
  hotel_id uuid not null references hotels(id) on delete cascade,
  fact_key text not null,
  field text not null,
  value text,
  snapshot_id uuid references hotel_snapshots(id) on delete set null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table topics (
  id uuid primary key default gen_random_uuid(),
  kind text not null,
  region_id uuid references regions(id),
  title text not null,
  params jsonb not null default '{}',
  status text not null default 'planned' check (status in ('planned','generating','generated','failed')),
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index topics_title_trgm on topics using gin (title gin_trgm_ops);

create table articles (
  id uuid primary key default gen_random_uuid(),
  topic_id uuid references topics(id),
  status text not null default 'draft'
    check (status in ('draft','ready','needs_review','rejected','published','archived')),
  slug text not null unique,
  region_id uuid references regions(id),
  qa_report jsonb not null default '{}',
  fact_pack jsonb not null default '{}',
  published_at timestamptz,
  data_as_of timestamptz,
  ai_disclosure text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table article_i18n (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references articles(id) on delete cascade,
  lang text not null check (lang in ('id','en')),
  title text not null,
  summary text not null,
  body_md text not null,
  faq jsonb not null default '[]',
  meta_title text not null,
  meta_desc text not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (article_id, lang)
);
create index article_i18n_title_trgm on article_i18n using gin (title gin_trgm_ops);

create table claim_map (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references articles(id) on delete cascade,
  lang text not null,
  claim_id text not null,
  sentence text not null,
  fact_ref text[] not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table image_assets (
  id uuid primary key default gen_random_uuid(),
  article_id uuid not null references articles(id) on delete cascade,
  role text not null check (role in ('hero','support')),
  prompt text not null,
  negative_prompt text not null,
  ratio text not null,
  style text,
  alt_id text not null,
  alt_en text not null,
  url text,
  status text not null default 'prompt_only',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table social_accounts (
  id uuid primary key default gen_random_uuid(),
  channel text not null,
  external_user_id text not null,
  token_enc text not null,
  token_expires_at timestamptz,
  active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (channel, external_user_id)
);

create table social_posts (
  id uuid primary key default gen_random_uuid(),
  article_id uuid references articles(id) on delete cascade,
  channel text not null default 'threads',
  angle text not null,
  lang text not null default 'id',
  text text not null,
  topic_tag text not null,
  image_asset_id uuid references image_assets(id),
  link_url text not null,
  status text not null default 'draft'
    check (status in ('draft','ready','queued','publishing','published','failed','dead')),
  scheduled_for timestamptz,
  published_at timestamptz,
  external_post_id text,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index social_posts_status on social_posts(status, scheduled_for);

create table schedule_slots (
  id uuid primary key default gen_random_uuid(),
  channel text not null,
  slot_at timestamptz not null,
  social_post_id uuid references social_posts(id),
  status text not null,  -- queued | published | failed | skipped_late | skipped_empty | skipped_paused
  note text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique (channel, slot_at)
);

create table jobs (
  id uuid primary key default gen_random_uuid(),
  type text not null,
  payload jsonb not null default '{}',
  run_at timestamptz not null default now(),
  attempts int not null default 0,
  max_attempts int not null default 4,
  locked_at timestamptz,
  locked_by text,
  status text not null default 'pending' check (status in ('pending','running','succeeded','failed','dead')),
  error text,
  result jsonb,
  idempotency_key text unique,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index jobs_status_run_at on jobs(status, run_at);

create table run_logs (
  id uuid primary key default gen_random_uuid(),
  run_id text not null,
  stage text not null,
  status text not null,
  message text,
  llm_tokens_in int not null default 0,
  llm_tokens_out int not null default 0,
  llm_billed_tokens int not null default 0,
  cost_usd numeric(16,10) not null default 0,
  duration_ms int not null default 0,
  error text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
create index run_logs_created on run_logs(created_at desc);

create table settings (
  key text primary key,
  value jsonb not null,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

-- updated_at triggers + RLS on every table. The agent connects as table owner / service role
-- (bypasses RLS); anon and authenticated get no policies, so they read nothing directly.
do $$
declare t text;
begin
  foreach t in array array['regions','sources','raw_snapshots','hotels','hotel_snapshots','insights',
    'insight_refs','topics','articles','article_i18n','claim_map','image_assets','social_accounts',
    'social_posts','schedule_slots','jobs','run_logs','settings']
  loop
    execute format('create trigger %I_touch before update on %I for each row execute function touch_updated_at()', t, t);
    execute format('alter table %I enable row level security', t);
    execute format('grant select on %I to anon, authenticated', t);  -- Supabase default grants; RLS denies
  end loop;
end $$;
grant usage on schema public to anon, authenticated;

-- Seeds -------------------------------------------------------------------------------------
insert into regions(slug, name, parent_slug, bbox) values
  ('bali',      'Bali',       null,   array[114.40, -8.85, 115.75, -8.05]),
  ('ubud',      'Ubud',       'bali', array[115.22, -8.56, 115.31, -8.46]),
  ('canggu',    'Canggu',     'bali', array[115.10, -8.67, 115.16, -8.61]),
  ('seminyak',  'Seminyak',   'bali', array[115.15, -8.70, 115.18, -8.67]),
  ('kuta',      'Kuta',       'bali', array[115.16, -8.75, 115.18, -8.70]),
  ('nusa-dua',  'Nusa Dua',   'bali', array[115.20, -8.83, 115.24, -8.77]),
  ('sanur',     'Sanur',      'bali', array[115.24, -8.73, 115.28, -8.66]),
  ('jimbaran',  'Jimbaran',   'bali', array[115.15, -8.80, 115.19, -8.76]),
  ('uluwatu',   'Uluwatu',    'bali', array[115.07, -8.85, 115.15, -8.79]),
  ('amed',      'Amed',       'bali', array[115.62, -8.36, 115.70, -8.32]),
  ('lovina',    'Lovina',     'bali', array[114.98, -8.17, 115.06, -8.14]);

insert into sources(key, tos_notes, license, attribution, cache_ttl_days, config) values
  ('overture',
   'Overture Maps Places, public S3 release read once per release via DuckDB. Attribution required. Re-sweep only when the release changes and >= 30 days passed.',
   'CDLA-Permissive-2.0 / Apache-2.0', 'Overture Maps Foundation', 30,
   '{"taxonomy_filter": "lodging"}'),
  ('osm',
   'OpenStreetMap via Overpass API: < 100 queries/day, >= 5 s between requests, no parallel queries, cache responses, honest User-Agent, 429/504 -> wait >= 30 s. 1 sweep per month.',
   'ODbL-1.0', '© OpenStreetMap contributors', 30,
   '{"tourism": ["hotel","guest_house","hostel","resort"]}');

insert into settings(key, value) values
  ('kill_switch', 'false'),
  ('review_mode', 'false'),
  ('budget_daily_usd', '2.0'),
  ('active_hours', '[0, 24]'),
  ('blog_publish_per_day', '3'),
  ('style_guide', '"Jujur, hangat, informatif. Tanpa hiperbola. Sebut sumber data terbuka. Tidak ada klaim harga atau rating tamu."');
