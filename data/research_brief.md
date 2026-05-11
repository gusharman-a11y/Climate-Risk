# Climate-target research brief

This is the working list for the **external research workflow** (ChatGPT or Claude.ai with web search). The Claude Code session that built this tracker can't fetch the web — that's why we're outsourcing the research.

## Important context for whoever's running the research

The tracker **already has the SBTi public dataset loaded** from sciencebasedtargets.org/companies-taking-action. So for any SBTi company, we already know:

- Target wording (the full sentence)
- Validation status (Targets Set / Committed / Commitment Removed)
- Target year, base year (when present in SBTi data)
- Net-zero year (when present)
- Date committed / date updated

**Don't waste ChatGPT context restating what SBTi already provides.** The research needs to add **what SBTi doesn't already give us** — namely current company-disclosed detail from their own FY24/FY25 reports.

---

## Updated prompt — paste into ChatGPT

> Australia-listed companies. The user already has the SBTi public dataset (sciencebasedtargets.org/companies-taking-action), so they know each company's SBTi status, target wording, and target/base/net-zero years from SBTi itself.
>
> What the user needs you to research from **each company's own FY24 or FY25 sustainability/climate/annual reports** (not from SBTi):
>
> 1. **Latest reported Scope 1 and Scope 2 emissions** (most recent year)
> 2. **Base-year Scope 1+2 emissions** (the absolute tCO2e they're measuring against)
> 3. **Reduction achieved to date** — % below baseline at most recent reporting year
> 4. **Scope 3 status** — is there a Scope 3 target? What categories? What % reduction by when?
> 5. **Any changes/updates since SBTi snapshot** — e.g. did they recently remove a commitment, push a target back, raise ambition, achieve a milestone?
> 6. **Validation date / removal reason** — exact month/year if known
> 7. **BD-relevant signals** — sustainability-linked loans, climate transition plans rejected by shareholders, recent restatements, methodology changes, regulatory issues
>
> Search FY24 / FY25 sources (sustainability reports, climate transition action plans, annual reports published 2024 or 2025). Don't use older sources unless nothing newer exists. Skip the SBTi public dashboard — the user has it.
>
> Return one CSV row per company inside a single ```csv``` code fence:
>
> `Company Name,Latest Reported Year,Latest S1 (tCO2e),Latest S2 (tCO2e),Base Year,Base S1+S2 (tCO2e),% Reduction Achieved,Scope 3 Status,Recent Update Since SBTi Snapshot,BD Signals,Source URL,Confidence`
>
> **Confidence** = `High` / `Medium` / `Low` based on how clearly each field is documented in a recent primary source.
>
> If a value isn't clearly disclosed in the primary source, leave the cell empty rather than guessing. Use Confidence = Low for rows where multiple cells are empty.
>
> Output only the CSV in one code fence, no prose between rows.
>
> Here are the companies:
>
> [PASTE COMPANY NAMES HERE]

---

## What you actually need to look for in the CSV ChatGPT returns

Compared to before:

| Old prompt fields | New prompt fields |
|---|---|
| Stated Target Description (duplicates SBTi) | **Latest Reported Year + S1 + S2** (NEW — what SBTi doesn't have) |
| Stated Target Year (in SBTi) | **Base Year + Base S1+S2 (tCO2e)** (NEW — absolute numbers) |
| Stated Net-Zero Year (in SBTi) | **% Reduction Achieved** (NEW — progress not target) |
| Target Classification (we derive) | **Scope 3 Status** (NEW — detail SBTi rarely has) |
| Source URL ✓ | **Recent Update Since SBTi Snapshot** (NEW — change signal) |
| Confidence ✓ | **BD Signals** (NEW — qualitative context) |
| Notes ✓ | **Source URL + Confidence** ✓ |

The new CSV plugs **directly into the emissions cache** — Latest S1/S2 numbers populate the trajectory math (Required Reduction vs Actual), Base S1+S2 enables the gap-to-path calculation, and Scope 3 Status / Recent Update / BD Signals all surface in the company drill-down.

This is genuinely additive over SBTi rather than redundant.

---

## Remaining companies to research (102 SBTi + ~340 non-SBTi)

Priority order — see `data/research_backlog.csv` for the full ranked list.

**Next batch (Batch 3, 36 companies — first half of Australian private SBTi cohort):**

```
APOG Topco Pty Ltd
Accolade Wines
Airmaster Corporation Pty Ltd
Allens
Alsco Uniforms
Ausgrid Group
Australian Broadcasting Corporation
Australian Postal Corporation
B2R Local No.1 Pty Ltd
BAI Communications Pty Ltd
BDO Group Holdings Limited
BIC Consolidated
Baiada Pty Ltd
Bank Australia
Bundaberg Sugar Ltd
CURA Day Hospitals Group Pty Ltd
CyberCX Pty Ltd
Campus Living Villages
Cement Australia Pty Ltd
Cirka
Compnow
Consolidated Property Services (Australia) Pty Ltd
Culture Amp
Edge Environment Pty Ltd
Erilyan Group Pty Ltd
FDC Group Holdings Pty Ltd
Frasers Property Australia
Fitness Passport
Frasers Property Industrial
GHD Group Limited
GeelongPort
Glad Group
Great Southern Bank
Grosvenor Engineering Group Pty Ltd
HSK Ward Group Pty Ltd
Hall & Wilcox
```

**Heads-up on private companies:** many of these are professional services firms (Allens, Hall & Wilcox, KWM, BDO, GHD), SMEs (BIC, Cirka, Compnow), or government entities (NBN, ABC, Australia Post, water utilities). Expect a higher hit rate of "No public target" / "Aspirational" — their direct emissions are small and few publish detailed climate reports. That's a useful BD signal itself though — they're SBTi-committed but lacking implementation infrastructure.

## When ChatGPT returns CSV

Paste back here. I'll:

1. Validate columns
2. Append/replace in the right cache files:
   - **Emissions** (Latest S1/S2/Base) → `data/emissions_cache.json` (populates trajectory math)
   - **Target metadata** (Scope 3, Recent Update, BD Signals) → new file `data/sbti_target_metadata.csv`
3. Commit and confirm coverage
