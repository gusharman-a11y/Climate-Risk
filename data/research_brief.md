# Climate-target research brief

This is the working list for the **external research workflow** (ChatGPT or Claude.ai with web search). The Claude Code session that built this tracker can't fetch the web — that's why we're outsourcing the research.

## What's already verified — DON'T research these

The cohort has 524 companies total. **128 already have credible target data and should be skipped:**

- **All SBTi-validated** companies (Near-term Status = "Targets set"). The SBTi public dataset is the authoritative source — no value re-researching them.
- **17 companies** verified via this workflow already (in `data/climate_targets_research.csv`): Appen, ASX Ltd, Australian Ethical, Downer EDI, Flight Centre, Fortescue, Inghams, Metrics Credit, nib, Stockland, Vicinity, Woodside, Glencore Holdings, Cleanaway, Stanmore, Coronado, SGH.
- **High-confidence training-data ASX 200 non-SBTi** (CBA, Westpac, NAB, ANZ, Macquarie, BHP, Rio, Santos, Wesfarmers, AGL, GPT, Amcor, BlueScope, Treasury Wine, ResMed etc.) — already documented well enough that the Confidence flag is "High" in `data/asx200_non_sbti.csv`.

## What needs research — 396 companies, prioritised

**`data/research_backlog.csv`** has the full list with priority scores. Headline counts:

| Bucket | Count | Priority | Notes |
|---|---|---|---|
| **Aus Corporate / FI (SBTi private), Commitment Removed** | 17 | 75 | Private firms whose SBTi commitment was withdrawn — likely have a current internal target |
| **Aus Corporate / FI (SBTi private), Committed only** | 23 | 70 | SBTi intent letter submitted but not yet validated |
| **ASX 200 non-SBTi** (Low/Medium-confidence training data) | 57 | 60 | My training-data classifications were uncertain; verify or upgrade |
| **NGER-only** (no overlay yet) | 299 | scaled by Scope 1 | Big direct emitters; foreign subsidiaries, state utilities, private mining/power |

**Note:** All 11 high-priority ASX-listed SBTi cohort entries (Fortescue, Vicinity, Stockland etc.) are now done — they're not in the backlog.

## Workflow per batch

1. Open ChatGPT or claude.ai (whichever has live web search you prefer)
2. Paste the prompt below
3. Append 30–50 company names from `data/research_backlog.csv` (top of the file = highest priority)
4. The chatbot returns a CSV in a code fence
5. Append the CSV to `data/climate_targets_research.csv` via GitHub web upload (commits append; existing rows aren't overwritten unless duplicate)
6. Streamlit auto-redeploys — researched targets override training-data values across all cohorts

## Prompt to use

> I need current climate targets for the Australian companies listed below. Search the web with strong preference for **FY24 or FY25 sources** (sustainability reports, annual reports, climate transition plans published in 2024 or 2025). Don't use older sources unless nothing newer exists.
>
> Return one CSV row per company inside a single ```csv``` code fence with these columns (use commas; double-quote any field containing a comma):
>
> `Company Name,Stated Target Description,Stated Target Year,Stated Net-Zero Year,Target Classification,Source URL,Confidence,Notes`
>
> **Target Classification** must be one of: `SBTi committed` | `Quantitative non-validated` | `Net-zero only` | `Aspirational` | `No public target`
>
> **Confidence** — `High` / `Medium` / `Low`.
>
> **Stated Target Description** — 1–2 sentences with headline number, base year, target year. Don't restate company background.
>
> **Source URL** — the actual sustainability/climate report URL, not the homepage.
>
> Output only the CSV in one code fence, no prose between rows.

## Suggested first batch — top 30 from the new backlog

```
The Arnotts Group
South East Water
Teachers Mutual Bank
SMEC ANZ
Intrepid Travel
B2R Local No.1 Pty Ltd
IPEC Pty Ltd (Team Global Express)
Icon Construction
Cement Australia Pty Ltd
Consolidated Property Services (Australia) Pty Ltd
BAI Communications Pty Ltd
Airmaster Corporation Pty Ltd
SECURECORP Pty Ltd
Yarra Valley Water
Partners in Performance
Nando's Australia Pty Ltd
Accolade Wines
NEXTDC
Scentre Group
Spark New Zealand
Orica
Fisher & Paykel Healthcare
TechnologyOne
Charter Hall Group
IGO Limited
Viva Energy Group
Ampol
Endeavour Group
Metcash
Worley
```

After this batch, take the top 30 NGER-only entries from the backlog file (sorted by priority desc) — they're the largest emitters in that cohort.
