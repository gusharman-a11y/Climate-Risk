# Research request — Climate targets for ASX cohort

This is a copy-paste prompt for **Claude.ai chat** (the chat product with web search, distinct from the Claude Code session that built this tracker). The Claude Code session can't fetch the web; Claude.ai can.

## Workflow

1. Open https://claude.ai in a new tab
2. Start a new chat
3. Paste the **prompt below**
4. Paste a **batch of company names** from `data/research_backlog.csv` (30–50 at a time works well — long lists may exceed context)
5. Claude.ai will search the web and return a CSV-formatted block
6. Copy the CSV output, paste back into this Claude Code chat
7. I'll merge it into the appropriate enrichment file (`asx200_non_sbti.csv` for cohorts 1–3, `nger_targets.csv` for cohort 4) and commit

---

## Prompt to paste into Claude.ai

> I need you to research current climate targets for a list of Australian companies. Search the web with a strong preference for FY24/FY25 sources (annual reports, sustainability reports, climate transition action plans published in 2024 or 2025). Don't use older sources unless nothing newer exists.
>
> For each company, return one CSV row with these columns (use commas; quote any field containing a comma):
>
> ```
> Company Name,Stated Target Description,Stated Target Year,Stated Net-Zero Year,Target Classification,Source URL,Confidence,Notes
> ```
>
> **Target Classification** must be exactly one of:
>
> - `SBTi committed` — submitted intent letter to SBTi but not yet validated
> - `Quantitative non-validated` — has a specific %/year reduction target, but not SBTi-validated
> - `Net-zero only` — has a long-term net-zero year but no specific near-term reduction target
> - `Aspirational` — vague climate ambition, no quantified specifics
> - `No public target` — limited or no public climate disclosure
>
> **Confidence** is `High` / `Medium` / `Low` based on how clearly the target is documented in a recent (FY24/FY25) primary source.
>
> **Stated Target Description** should be 1–2 sentences capturing the headline number, base year, and target year if quantitative. E.g. *"30% absolute Scope 1+2 reduction by 2030 from FY20 baseline; net zero ops by 2050"*. Don't restate company background — just the target.
>
> **Source URL** should be the actual sustainability report or climate report URL — not the company homepage.
>
> Please output the CSV inside a single ```csv code fence so it's easy for me to copy. Don't include explanatory prose between rows. If a company genuinely has no public target after a thorough search, return `No public target` with `Confidence=High` and a brief note why.
>
> Here is the list of companies to research:
>
> [PASTE COMPANY NAMES HERE — one per line]

---

## Priority list (top 100 from `data/research_backlog.csv`)

Tackle these in priority order. The ASX-listed SBTi cohort (priority 100) should be researched first — these are companies that *had* SBTi commitments but removed them or are committed-only, so the public sources will be richest.

### Tier-1 priorities — ASX-listed (SBTi cohort but no validated target)

These are SBTi-committed or commitment-removed cases where the climate strategy is publicly disclosed but not validated.

```
Appen Limited
ASX Limited
Australian Ethical Investment
Downer EDI Limited
Flight Centre Travel Group
Fortescue Metals Group Ltd
Inghams Group Ltd
Metrics Credit Partners
nib holdings limited
Stockland Corporation Limited and Stockland Trust
Vicinity Centres
```

### Tier-2 priorities — large NGER-only emitters without overlay

These are big direct emitters where target verification has high BD value.

```
[run: python -c "import pandas as pd; df = pd.read_csv('data/research_backlog.csv'); print(df[df['Cohort']=='NGER reporters (not in cohort)'].head(60)['Company Name'].to_string(index=False))"]
```

### Tier-3 priorities — Australian Corporate / FI (SBTi private)

Privately-held SBTi entities. Smaller individual emissions but each is an SBTi participant by definition, so disclosure exists.

---

## After Claude.ai returns CSV

Paste the entire CSV block (including the ```csv fences) back into this Claude Code chat. I'll:

1. Validate the columns
2. Merge by company name (fuzzy-matched against the cohort)
3. Commit to the appropriate enrichment file
4. Re-run the cohort build to confirm coverage

Roughly 100–150 companies per hour of Claude.ai chat time, depending on how cooperative the corporate sites are with web search.
