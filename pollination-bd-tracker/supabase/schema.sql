-- Pollination BD Tracker — Supabase Schema
-- Run this in the Supabase SQL editor to initialise the database.

create extension if not exists "uuid-ossp";

-- ── Companies ─────────────────────────────────────────────────────────────────
create table if not exists companies (
  id                      uuid primary key default uuid_generate_v4(),
  abn                     text,
  name                    text not null,
  asx_code                text,
  sector                  text,
  industry                text,
  is_listed               boolean default false,
  is_private              boolean default false,
  -- Size
  market_cap_tier         text,
  revenue_aud             numeric,
  assets_aud              numeric,
  employee_count          integer,
  -- ASRS
  asrs_group              text default 'Unclassified',
  mandatory_from          date,
  -- Emissions
  nger_scope1_tco2e       numeric,
  nger_year               text,
  safeguard_covered       boolean default false,
  safeguard_baseline      numeric,
  -- Climate target
  sbti_status             text,
  sbti_date_updated       date,
  target_classification   text,
  target_year             integer,
  net_zero_year           integer,
  -- NZT overlay
  nzt_end_target          text,
  nzt_end_year            integer,
  nzt_status              text,
  nzt_interim_pct         numeric,
  nzt_published_plan      boolean,
  nzt_race_to_zero        boolean,
  -- Relationship
  relationship_status     text not null default 'none'
                          check (relationship_status in ('current_client','past_client','warm_contact','none')),
  relationship_lead       text,
  relationship_contacts   text,
  relationship_notes      text,
  last_interaction_date   date,
  -- Pipeline
  pipeline_stage          text
                          check (pipeline_stage in ('watch','prospect','qualified','proposal','negotiation','mandated','missed')),
  pipeline_owner          text,
  pipeline_notes          text,
  pipeline_next_action    text,
  pipeline_next_action_date date,
  -- Scores (computed by seed/refresh script)
  score_asrs              numeric(3,1),
  score_target_gap        numeric(3,1),
  score_risk              numeric(3,1),
  score_intent            numeric(3,1),
  score_relationship      numeric(3,1),
  score_overall           numeric(4,2),
  top_signal              text,
  -- Metadata
  created_at              timestamptz default now(),
  updated_at              timestamptz default now()
);

create index if not exists idx_companies_asrs_group on companies(asrs_group);
create index if not exists idx_companies_score on companies(score_overall desc);
create index if not exists idx_companies_pipeline on companies(pipeline_stage);
create index if not exists idx_companies_relationship on companies(relationship_status);

-- ── Signals ───────────────────────────────────────────────────────────────────
create table if not exists signals (
  id           uuid primary key default uuid_generate_v4(),
  company_id   uuid not null references companies(id) on delete cascade,
  signal_type  text not null,
  signal_date  date not null,
  headline     text not null,
  body         text,
  source_url   text,
  source       text,
  score_delta  numeric(3,1) default 0,
  created_at   timestamptz default now()
);

create index if not exists idx_signals_company on signals(company_id);
create index if not exists idx_signals_date on signals(signal_date desc);

-- ── Auto-update updated_at ─────────────────────────────────────────────────
create or replace function update_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

create or replace trigger companies_updated_at
  before update on companies
  for each row execute function update_updated_at();
