# Pollination BD Tracker — Build Progress
_Last updated: June 2026_

---

## What's been built

### App
Next.js 16 app at `C:\Users\angus.harman\Climate-Risk\pollination-bd-tracker\`
GitHub branch: `feature/bd-tracker` on `gusharman-a11y/Climate-Risk`

**3 pages working:**
- `/` — Hot sheet: companies ranked by BD score, grouped by ASRS Group, Monday.com style
- `/companies` — Full searchable/filterable universe of 2073 companies
- `/companies/[id]` — Company profile: score breakdown, signal timeline, relationship panel, pipeline stage editor
- `/pipeline` — Kanban board across 7 stages

**Stack:** Next.js 16, Supabase (Postgres), Tailwind 4, shadcn/ui, Figtree font
**Design:** Monday.com — white top nav, light grey background #f6f7fb, Monday blue #0073ea

---

## Database (Supabase)
**Project URL:** `https://ahoyjvqvgbmcoydjgzpb.supabase.co`
**Tables:** `companies` (2073 rows), `signals` (empty — manual entry only so far)
**Keys:** in `.env.local` (not committed to git)

---

## Scoring system
5 categories, each 1–5, overall = average → displayed as X/5

| Category | What drives it |
|----------|---------------|
| ASRS urgency | Group 1=5, Group 2=4, Group 3=2, Unclassified=1 |
| Target gap | No target=5, Aspirational/Old SBTi=4, Net-zero only=4, Quantitative non-validated=2, Committed=3, Validated=1 |
| Risk signals | SBTi removed=5, Greenwashing=5, Safeguard covered=4, Target imminent=3 |
| Intent signals | Race to Zero=3, NZT published plan=2 |
| Relationship | Past client=4, Warm contact=3, Cold=1, Current client=0 (excluded from hot sheet) |

**To change weights:** edit `scoring.config.json` then run `py scripts/rescore.py`
**Rescore takes ~3 minutes** (2073 companies, one update per row via Supabase REST)

---

## Data sources loaded

| Source | File | Companies | Status |
|--------|------|-----------|--------|
| ASX full listing | `data/ASXListedCompanies.csv` | 1976 | ✅ Loaded |
| ASX200 target research | `data/asx200_non_sbti.csv` | 74 | ✅ Loaded |
| NGER large emitters | `data/nger_targets.csv` | 57 | ✅ Loaded |
| SBTi global database | `data/sbti_companies.xlsx` | 157 AU | ✅ Loaded |
| Net Zero Tracker | `data/nzt_snapshot.xlsx` | 32 AU | ✅ Loaded |
| Company financials | `data/company_size.csv` | 134 | ✅ Used for ASRS classification |
| BD Tracker Excel | `Downloads/Pollination_BD_Tracker_June2026.xlsx` | — | ✅ Relationships + pipeline seeded |

**Relationship data seeded:**
- 36 current engagements (excluded from hot sheet)
- 18 pipeline entries (in kanban)
- 23 strategic accounts with Pollination lead names

---

## Known issues / next steps

### 1. Progress to target — NOT BUILT YET
The delivery gap signal (are they on track for their SBTi?) is the most valuable signal.
Needs:
- NGER Scope 1 emissions matched to company targets
- Linear path calculation: `expected_reduction = (years_elapsed / total_years) × target_pct`
- Compare actual (NGER) vs expected → delivery gap score
- The Python logic already exists in `../modules/bd_insights.py` (`behind_on_delivery`)
- Needs to be ported into `scripts/rescore.py`

### 2. Scores still low (max ~3.8)
- Intent and risk signals are weak — most companies score 1 on both
- To push companies to 4-5 need manual signals: greenwashing cases, ASRS mentioned in report
- Signal entry UI exists on company profile but signals table is empty
- Phase 2: ASX announcement scraper to auto-populate signals

### 3. ASRS group classification
- Fixed: ASX200 + NGER + company_size.csv used as proxies
- Still ~600 companies "Unclassified" — small ASX companies without financial data
- These are genuinely uncertain — may not meet ASRS thresholds

### 4. SBTi vintage signal
- `sbti_date_updated` loaded for 157 AU companies
- Pre-2023 validated targets flagged as score 4 (V2 refresh needed)
- Working correctly

### 5. Supabase cold start (~2s first load)
- Free tier pauses after inactivity
- Next.js cache added (2min for hot sheet, 5min for companies list)
- First load after inactivity will be slow — subsequent loads instant

---

## Scripts

| Script | What it does |
|--------|-------------|
| `scripts/seed_database.py` | Full re-seed from CSVs. Wipes and re-inserts all 2073 companies. |
| `scripts/rescore.py` | Re-scores all companies using `scoring.config.json`. Run after editing weights. ~3 min. |
| `scripts/check_hotsheet.py` | Prints top 20 companies to terminal for sanity checking. |
| `supabase/schema.sql` | Database schema — run in Supabase SQL editor to recreate tables. |

---

## How to run locally

```bash
cd C:\Users\angus.harman\Climate-Risk\pollination-bd-tracker
npm run dev
# Open http://localhost:3000
```

Requires `.env.local` with Supabase URL, anon key and secret key.
See `.env.local.example` for the format. Keys are in your local `.env.local` (not committed).

---

## Decisions made (for context in next chat)

- **No Pollination branding** — Monday.com design language throughout
- **Supabase not Vercel Postgres** — consistent with ASRS gap tool, has table editor UI
- **Scoring is static** (calculated at seed/rescore time, stored in DB) — not dynamic per request
- **Relationship status:** current_client / past_client / warm_contact / none
  - Current clients excluded from hot sheet entirely
  - Relationship is a score multiplier, not a separate filter
- **Pipeline stages:** watch / prospect / qualified / proposal / negotiation / mandated / missed
  - Matches Pollination BD Excel stages
- **NZT snapshot** saved at `data/nzt_snapshot.xlsx` (downloaded June 7 2026)
  - Re-download from zerotracker.net when stale, replace file, re-run seed
- **SBTi vintage scoring:** pre-2023 validated = score 4 (V2 refresh signal)
- **ASRS group classification hierarchy:** actual financials → ASX200 proxy → NGER proxy → market cap tier → Unclassified

---

## Conversation context (what was discussed)

This was built across one long conversation. Key design decisions:
1. Started as discussion of data sources and architecture — user (Gus) wanted to plan before building
2. Monday.com as explicit design reference — confirmed twice
3. No Pollination branding — user preference
4. Supabase chosen over Vercel Postgres for table editor + consistency
5. Scoring: 1-5 per category, average overall (not weighted sum)
6. SBTi vintage added as signal after research into how TPI/CA100+ assess companies
7. NZT data integrated — 32 AU companies with intent/plan signals
8. BD Excel (June 2026) seeded for existing relationships and pipeline

**Next priorities (in order):**
1. Delivery progress to target calculation (port from Python bd_insights.py)
2. Manual signal entry — add greenwashing cases, ASRS mentions for top prospects
3. Deploy to Vercel for team sharing
4. ASX announcement scraper for auto-signals (Phase 2)
