# Pollination BD Tracker — Build Progress
_Last updated: June 2026_

---

## What's been built

### App
Next.js 16 app at `C:\Users\angus.harman\Climate-Risk\pollination-bd-tracker\`
GitHub branch: `feature/bd-tracker` on `gusharman-a11y/Climate-Risk`

**4 pages working:**
- `/` — Hot sheet: companies ranked by BD score, grouped by ASRS Group, Monday.com style
- `/companies` — Full searchable/filterable universe of 2073 companies
- `/companies/[id]` — Company profile: score breakdown, signal timeline, relationship panel, pipeline stage editor
- `/pipeline` — Kanban board across 7 stages

**Stack:** Next.js 16, Supabase (Postgres), Tailwind 4, Figtree font
**Design:** Monday.com — white top nav, light grey background #f6f7fb, Monday blue #0073ea

---

## Database (Supabase)
**Project URL:** `https://ahoyjvqvgbmcoydjgzpb.supabase.co`
**Tables:** `companies` (2073 rows), `signals` (empty — manual entry only so far)
**Keys:** in `.env.local` (not committed to git)

**Schema additions needed (run in Supabase SQL editor if not done):**
```sql
alter table companies add column if not exists target_description text;
alter table companies add column if not exists target_scope text;
```

---

## Scoring system
Weighted average: ASRS×0.25 + TargetGap×0.30 + Risk×0.25 + Intent×0.10 + Rel×0.10

| Category | What drives it |
|----------|---------------|
| ASRS urgency | Group 1=5, Group 2=3, Group 3=2, Unclassified=1 |
| Target gap | No target/SBTi removed=5, Aspirational/Old SBTi pre-2023=4, Net-zero only=4, Committed=3, 2023-24 validated=3, Quantitative non-validated=2, Targets set=1 |
| Risk signals | SBTi removed/greenwashing=5, Safeguard=4, target imminent=3, delivery behind=3 |
| Intent signals | ASRS in report=5, AGM climate item=4, Race to Zero=3, NZT plan=2 |
| Relationship | Past client=5, Warm contact=3, Cold=1, Current client=0 (excluded) |

**To change weights:** edit `scoring.config.json` → run `py scripts/enrich_database.py`
**Current top scores:** Stockland 4.4, Fortescue 4.3, ASX/Downer/Inghams 4.2, Cleanaway 4.0

---

## Data sources loaded

| Source | File | Companies | Status |
|--------|------|-----------|--------|
| ASX full listing | `data/ASXListedCompanies.csv` | 1976 | ✅ Loaded |
| ASX200 target research | `data/asx200_non_sbti.csv` | 74 | ✅ Loaded |
| NGER 2024-25 emissions | `data/nger_2024_25.xlsx.xlsx` | 199 matched | ✅ Loaded |
| Safeguard baselines | `data/cer/baselines-and-emissions.csv` | 78 facilities | ✅ Loaded |
| SBTi global database | `data/sbti_companies.xlsx` | 157 AU total, 14 matched | ⚠️ Matching issue |
| Net Zero Tracker | `data/nzt_snapshot.xlsx` | 32 AU | ✅ Loaded |
| Company financials | `data/company_size.csv` | 134 | ✅ Used for ASRS classification |
| BD Tracker Excel | `Downloads/Pollination_BD_Tracker_June2026.xlsx` | — | ✅ Relationships + pipeline seeded |
| Target descriptions | `asx200_non_sbti.csv` + `nger_targets.csv` | ~74 | ⚠️ Needs backfill script run |

---

## Known issues — PRIORITY ORDER

### 1. SBTi validated companies not on hot sheet ← NEXT TO FIX
**Root cause:** 143 of 157 AU SBTi companies unmatched (mostly private — not in ASX universe).
Only 50 DB companies have `sbti_status = 'Targets set'`, scoring ~3.2 — buried below 4.2+ no-target companies.

**Fix needed:**
- Insert unmatched SBTi companies as new DB records (they're private companies like Allens, Brambles, Ausgrid)
- Add a dedicated **"SBTi Validated — V2 Refresh Needed"** section on the hot sheet for pre-2023 validated companies, sorted by validation date (oldest first). These are a different BD conversation, shouldn't compete on score.

**Script to write:** `scripts/add_sbti_private_companies.py` — inserts unmatched AU SBTi companies

### 2. Target descriptions not yet backfilled
Run: `py scripts/backfill_targets.py` (after adding DB columns above)
Also need scope inference fix — Fortescue shows 2030 net zero (that's S1+S2 only; NZT shows 2040)

### 3. Delivery progress to target — not calculated
Linear path calc exists in `../modules/bd_insights.py`. Needs base year emissions from company research.

### 4. Signals table empty
Manual signal entry UI built but no data. Need to add 10-15 signals for top prospects:
- Greenwashing cases (ACCC enforcement)
- ASRS mentioned in sustainability reports
- Shareholder resolutions

### 5. App startup slow
Dev server takes 20-30s first compile. Normal for Turbopack cold start.
`@import "shadcn/tailwind.css"` removed — was causing 10min hang. Now compiles fast.

### 6. Deploy to Vercel — not done yet
Needed for team sharing. Steps: connect repo → add env vars → deploy.

---

## Scripts

| Script | What it does | When to run |
|--------|-------------|-------------|
| `scripts/seed_database.py` | Full re-seed from all CSVs. Wipes and re-inserts 2073 companies. | First setup only |
| `scripts/enrich_database.py` | **Main script.** NGER + Safeguard + SBTi + rescore. | After data refresh |
| `scripts/backfill_targets.py` | Adds target_description + target_scope from research CSVs | After adding DB columns |
| `scripts/rescore.py` | Rescore only (no data enrichment). | After changing scoring.config.json |
| `scripts/diagnose.py` | Shows data coverage stats. | Debugging |
| `scripts/diagnose_sbti.py` | Shows SBTi matching + scoring analysis. | Debugging |
| `scripts/check_hotsheet.py` | Prints top 20 companies to terminal. | Sanity check |
| `supabase/schema.sql` | DB schema. | First setup only |

---

## How to run locally

```bash
cd C:\Users\angus.harman\Climate-Risk\pollination-bd-tracker
npx next dev
# Open http://localhost:3000
```

`.env.local` has Supabase URL, anon key and secret key (not committed to git).

---

## Architecture decisions

- **No Pollination branding** — Monday.com design throughout
- **Supabase** — consistent with ASRS gap tool, has table editor UI
- **Scoring is static** — calculated at enrichment time, stored in DB
- **Weighted formula** (not flat average): ASRS×0.25, TargetGap×0.30, Risk×0.25, Intent×0.10, Rel×0.10
- **Relationship:** current_client excluded from hot sheet; past_client=5, warm=3, cold=1
- **SBTi vintage:** pre-2023 validated = score 4 (V2 refresh signal)
- **ASRS group hierarchy:** actual financials → ASX200 proxy → NGER proxy → market cap tier → Unclassified
- **Pipeline stages:** watch/prospect/qualified/proposal/negotiation/mandated/missed

## Hot sheet groups (current + planned)
1. Group 1 — Mandatory NOW
2. Group 2 — Mandatory FY2026/27
3. Group 3 — Mandatory FY2027/28
4. **SBTi Validated — V2 Refresh** ← TO BUILD (pre-2023 validated, sorted oldest first)
5. Unclassified

---

## Immediate next session tasks
1. `scripts/add_sbti_private_companies.py` — insert 143 unmatched AU SBTi companies
2. Add "SBTi V2 Refresh" group to hot sheet UI (HotSheetClient.tsx)
3. Run `py scripts/backfill_targets.py` (after adding DB columns in Supabase)
4. Deploy to Vercel
