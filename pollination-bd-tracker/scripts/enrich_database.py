"""
Enrich the BD Tracker database with:
1. NGER 2024-25 Scope 1 + Scope 2 emissions (matched by name)
2. Safeguard baselines + covered facility flag (matched by responsible emitter)
3. SBTi status fix (re-match all 157 AU SBTi companies with fuzzy matching)
4. Re-score all companies with the enriched data

Run this after seed_database.py, or whenever source data is refreshed.
Usage: py scripts/enrich_database.py
"""
from __future__ import annotations
import os, re, math
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "data"
CER = DATA / "cer"

for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── Name normalisation ────────────────────────────────────────────────────────
_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|group|"
    r"holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|australia|"
    r"australian|pty|energy|resources|services|operations|holdings)\b", re.I
)

def nkey(n: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(n).lower())
    n = _STRIP.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

def fuzzy_match(target_key: str, lookup: dict, min_len: int = 4) -> str | None:
    if target_key in lookup:
        return target_key
    if len(target_key) < min_len:
        return None
    prefix = target_key[:min(6, len(target_key))]
    for k in lookup:
        if k.startswith(prefix) or target_key.startswith(k[:min(6, len(k))]):
            # Require meaningful word overlap
            ta, tb = set(target_key.split()), set(k.split())
            if len(ta & tb) >= max(1, min(len(ta), len(tb)) - 1):
                return k
    return None

# ── Load NGER 2024-25 ─────────────────────────────────────────────────────────
print("Loading NGER 2024-25 emissions data...")
nger_raw = pd.read_excel(DATA / "nger_2024_25.xlsx.xlsx", header=2)
nger_raw.columns = ["name", "abn", "scope1", "scope2", "energy", "notes"]
nger_raw = nger_raw.dropna(subset=["name", "scope1"])
nger_raw = nger_raw[nger_raw["name"].astype(str).str.len() > 2]
nger_raw["scope1"] = pd.to_numeric(nger_raw["scope1"], errors="coerce")
nger_raw["scope2"] = pd.to_numeric(nger_raw["scope2"], errors="coerce")
nger_raw = nger_raw.dropna(subset=["scope1"])

nger_lookup = {}
for _, row in nger_raw.iterrows():
    k = nkey(str(row["name"]))
    if k and k not in nger_lookup:
        nger_lookup[k] = {
            "nger_scope1_tco2e": float(row["scope1"]),
            "nger_scope2_tco2e": float(row["scope2"]) if pd.notna(row["scope2"]) else None,
            "nger_year": "FY2024-25",
        }

print(f"  NGER companies: {len(nger_lookup)}")

# ── Load Safeguard baselines ───────────────────────────────────────────────────
print("Loading Safeguard baselines...")
sg_raw = pd.read_csv(CER / "baselines-and-emissions.csv")
sg_lookup = {}
for _, row in sg_raw.iterrows():
    emitter = str(row.get("Responsible emitter", "")).strip()
    if not emitter:
        continue
    k = nkey(emitter)
    baseline_str = str(row.get("Baseline emissions number", "")).replace(",", "").strip()
    covered_str = str(row.get("Covered emissions", "")).replace(",", "").strip()
    try:
        baseline = float(baseline_str)
    except ValueError:
        baseline = None
    try:
        covered = float(covered_str)
    except ValueError:
        covered = None

    if k not in sg_lookup:
        sg_lookup[k] = {"safeguard_covered": True, "safeguard_baseline": baseline, "safeguard_covered_emissions": covered}
    else:
        # Multiple facilities — sum baselines
        if baseline and sg_lookup[k]["safeguard_baseline"]:
            sg_lookup[k]["safeguard_baseline"] += baseline
        if covered and sg_lookup[k].get("safeguard_covered_emissions"):
            sg_lookup[k]["safeguard_covered_emissions"] += covered

print(f"  Safeguard emitters: {len(sg_lookup)}")

# ── Load SBTi AU companies ─────────────────────────────────────────────────────
print("Loading SBTi AU companies...")
sbti_raw = pd.read_excel(DATA / "sbti_companies.xlsx")
sbti_au = sbti_raw[sbti_raw["location"] == "Australia"].copy()
sbti_lookup = {}
for _, row in sbti_au.iterrows():
    k = nkey(str(row["company_name"]))
    if k:
        sbti_lookup[k] = {
            "sbti_status": str(row.get("near_term_status") or ""),
            "sbti_date_updated": str(row["date_updated"])[:10] if pd.notna(row.get("date_updated")) else None,
        }

print(f"  SBTi AU companies: {len(sbti_lookup)}")

# ── Load all companies from Supabase ─────────────────────────────────────────
print("Loading companies from Supabase...")
BATCH = 1000
all_companies = []
offset = 0
while True:
    r = sb.table("companies").select(
        "id,name,asrs_group,market_cap_tier,sbti_status,sbti_date_updated,"
        "target_classification,target_year,nger_scope1_tco2e,"
        "safeguard_covered,nzt_published_plan,nzt_race_to_zero,relationship_status"
    ).range(offset, offset + BATCH - 1).execute()
    all_companies.extend(r.data)
    if len(r.data) < BATCH:
        break
    offset += BATCH

print(f"  Total companies: {len(all_companies)}")

# ── Match and enrich each company ─────────────────────────────────────────────
import json
cfg = json.loads((ROOT / "scoring.config.json").read_text())

SIZE_DATA = DATA / "company_size.csv"
size_df = pd.read_csv(SIZE_DATA)
SIZE_LOOKUP = {nkey(r["Company Name"]): dict(r) for _, r in size_df.iterrows()}

asx200 = pd.read_csv(DATA / "asx200_non_sbti.csv")
ASX200_KEYS = {nkey(n) for n in asx200["Company Name"]}
nger_targets = pd.read_csv(DATA / "nger_targets.csv")
NGER_TARGET_KEYS = {nkey(n) for n in nger_targets["NGER Reporting Entity"]}
MC_MAP = {"mega": "Group 1", "large": "Group 1", "mid": "Group 2", "small": "Group 3", "micro": "Group 3"}

def classify_asrs(row: dict, nk: str) -> str:
    existing = row.get("asrs_group", "")
    if existing in ("Group 1", "Group 2", "Group 3"):
        return existing
    # Financial data
    size = SIZE_LOOKUP.get(nk)
    if not size:
        mk = fuzzy_match(nk, SIZE_LOOKUP)
        if mk:
            size = SIZE_LOOKUP[mk]
    if size:
        rev = float(size.get("Revenue (AUD)") or 0)
        ast = float(size.get("Assets (AUD)") or 0)
        emp = float(size.get("Employees") or 0)
        if (rev >= 500e6) + (ast >= 1e9) + (emp >= 500) >= 2:
            return "Group 1"
        if (rev >= 200e6) + (ast >= 500e6) + (emp >= 250) >= 2:
            return "Group 2"
        if (rev >= 50e6) + (ast >= 25e6) + (emp >= 100) >= 2:
            return "Group 3"
    if nk in ASX200_KEYS or fuzzy_match(nk, {k: 1 for k in ASX200_KEYS}):
        return "Group 1"
    if nk in NGER_TARGET_KEYS or fuzzy_match(nk, {k: 1 for k in NGER_TARGET_KEYS}):
        return "Group 2"
    mc = str(row.get("market_cap_tier") or "").lower().strip()
    return MC_MAP.get(mc, existing or "Unclassified")

def delivery_gap_score(scope1: float | None, target_pct: float | None,
                       base_year: int, target_year: int, base_emissions: float | None) -> float:
    """Return risk score boost from delivery gap. 0 if insufficient data."""
    if not all([scope1, target_pct, base_emissions, base_year, target_year]):
        return 0
    try:
        years_total = target_year - base_year
        years_elapsed = date.today().year - base_year
        if years_total <= 0 or years_elapsed <= 0:
            return 0
        expected_pct = (years_elapsed / years_total) * target_pct
        actual_pct = (1 - scope1 / base_emissions) * 100
        gap = expected_pct - actual_pct  # positive = behind
        if gap > 20:
            return 2   # significantly behind
        if gap > 10:
            return 1   # behind
    except Exception:
        pass
    return 0

def score_target_gap(sbti_status: str, target_class: str, sbti_date: str | None) -> float:
    s = str(sbti_status or "").lower()
    tc = str(target_class or "").strip()
    tg = cfg["target_gap"]
    if "removed" in s:
        return float(tg.get("sbti_removed", 5))
    if tc in tg:
        if tc == "Targets set" and sbti_date:
            try:
                yr = int(str(sbti_date)[:4])
                if yr < 2023:
                    return float(tg.get("sbti_pre_2023", 4))
                if yr < 2025:
                    return float(tg.get("sbti_2023_2024", 3))
            except Exception:
                pass
        return float(tg[tc])
    if "committed" in s:
        return float(tg.get("SBTi committed", 3))
    return float(tg.get("No public target", 5))

def score_risk(safeguard: bool, sbti_status: str, target_year, delivery_boost: float) -> float:
    rs = cfg["risk_signals"]
    s = str(sbti_status or "").lower()
    score = float(rs.get("default", 1))
    if safeguard:
        score = max(score, float(rs.get("safeguard_covered", 4)))
    if "removed" in s:
        score = max(score, float(rs.get("sbti_removed", 5)))
    try:
        if target_year and (int(target_year) - date.today().year) <= 2:
            score = max(score, float(rs.get("target_year_within_2_years", 3)))
    except Exception:
        pass
    score = min(5, score + delivery_boost)
    return score

def build_top_signal(stg, sr, sa, srel, sbti_s, tc, safeguard, scope1, delivery_boost) -> str:
    s = str(sbti_s or "").lower()
    candidates = []
    if "removed" in s:
        candidates.append((5, "SBTi commitment removed — re-engagement opportunity"))
    if delivery_boost >= 2:
        candidates.append((4.5, "Significantly behind SBTi delivery trajectory"))
    elif delivery_boost >= 1:
        candidates.append((4, "Behind on SBTi delivery trajectory"))
    if stg >= 4.5:
        candidates.append((4, f"No public climate target — ASRS mandatory disclosure required"))
    elif stg >= 3.5:
        candidates.append((3.5, f"Weak target ({tc}) — credibility gap under ASRS scrutiny"))
    if safeguard:
        candidates.append((3, "Safeguard Mechanism covered — legal reduction obligation"))
    if sa >= 5:
        candidates.append((2, "ASRS Group 1 — mandatory reporting this financial year"))
    elif sa >= 4:
        candidates.append((2, "ASRS Group 2 — mandatory from FY2026/27"))
    if srel >= 4:
        candidates.append((1, "Past client — warm re-engagement opportunity"))
    candidates.sort(key=lambda x: -x[0])
    return candidates[0][1] if candidates else "ASRS reporting obligation"

# ── Process all companies ─────────────────────────────────────────────────────
print("Enriching and rescoring...")
updates = []
nger_matched = 0
sg_matched = 0
sbti_matched = 0

for row in all_companies:
    nk = nkey(str(row.get("name", "")))
    patch: dict = {}

    # 1. NGER emissions
    nger = nger_lookup.get(nk) or (nger_lookup.get(fuzzy_match(nk, nger_lookup) or "") if fuzzy_match(nk, nger_lookup) else None)
    if nger:
        patch["nger_scope1_tco2e"] = nger["nger_scope1_tco2e"]
        patch["nger_year"] = nger["nger_year"]
        # scope2 not in schema yet — skip
        nger_matched += 1

    # 2. Safeguard
    sg = sg_lookup.get(nk) or (sg_lookup.get(fuzzy_match(nk, sg_lookup) or "") if fuzzy_match(nk, sg_lookup) else None)
    if sg:
        patch["safeguard_covered"] = True
        patch["safeguard_baseline"] = sg.get("safeguard_baseline")
        sg_matched += 1

    # 3. SBTi (only overwrite if we get a better match)
    existing_sbti = str(row.get("sbti_status") or "")
    sbti = sbti_lookup.get(nk) or (sbti_lookup.get(fuzzy_match(nk, sbti_lookup) or "") if fuzzy_match(nk, sbti_lookup) else None)
    if sbti and not existing_sbti:
        patch.update(sbti)
        sbti_matched += 1
    elif sbti:
        patch.update(sbti)  # Always update — SBTi data is authoritative

    # Build enriched row for scoring
    enriched = {**row, **patch}
    nk_row = nkey(str(enriched.get("name", "")))

    # 4. ASRS group classification
    enriched["asrs_group"] = classify_asrs(enriched, nk_row)

    # 5. Delivery gap
    scope1 = enriched.get("nger_scope1_tco2e") or patch.get("nger_scope1_tco2e")
    del_boost = delivery_gap_score(
        scope1,
        target_pct=None,   # TODO: load base year % from asx200 research
        base_year=2019,
        target_year=int(enriched.get("target_year") or 0),
        base_emissions=None,
    )

    # 6. Scores
    sa   = float(cfg["asrs_urgency"].get(enriched["asrs_group"], 1))
    stg  = score_target_gap(enriched.get("sbti_status", ""), enriched.get("target_classification", ""), enriched.get("sbti_date_updated"))
    sr   = score_risk(enriched.get("safeguard_covered", False), enriched.get("sbti_status", ""), enriched.get("target_year"), del_boost)
    si   = float(cfg["intent_signals"].get("default", 1))
    if enriched.get("nzt_race_to_zero"):
        si = max(si, float(cfg["intent_signals"].get("race_to_zero_member", 3)))
    if enriched.get("nzt_published_plan"):
        si = max(si, float(cfg["intent_signals"].get("nzt_published_plan", 2)))
    srel = float(cfg["relationship"].get(enriched.get("relationship_status", "none"), 1))
    w = cfg.get("weights", {"asrs_urgency":0.25,"target_gap":0.30,"risk_signals":0.25,"intent_signals":0.10,"relationship":0.10})
    overall = round(
        sa  * w.get("asrs_urgency",  0.25) +
        stg * w.get("target_gap",    0.30) +
        sr  * w.get("risk_signals",  0.25) +
        si  * w.get("intent_signals",0.10) +
        srel* w.get("relationship",  0.10),
    2)

    top_sig = build_top_signal(stg, sr, sa, srel,
                               enriched.get("sbti_status", ""),
                               enriched.get("target_classification", ""),
                               enriched.get("safeguard_covered", False),
                               scope1, del_boost)

    update = {
        "id": row["id"],
        "asrs_group": enriched["asrs_group"],
        "score_asrs": sa,
        "score_target_gap": stg,
        "score_risk": sr,
        "score_intent": si,
        "score_relationship": srel,
        "score_overall": overall,
        "top_signal": top_sig,
        **{k: v for k, v in patch.items() if k not in ("id",)},
    }
    updates.append(update)

print(f"  NGER emissions matched: {nger_matched}")
print(f"  Safeguard matched: {sg_matched}")
print(f"  SBTi re-matched: {sbti_matched}")
print(f"  Updating {len(updates)} companies...")

# ── Push to Supabase ──────────────────────────────────────────────────────────
for i, upd in enumerate(updates):
    row_id = upd.pop("id")
    # Clean nulls
    clean = {k: v for k, v in upd.items() if v is not None and not (isinstance(v, float) and math.isnan(v))}
    sb.table("companies").update(clean).eq("id", row_id).execute()
    if (i + 1) % 200 == 0:
        print(f"  {i+1}/{len(updates)}")

print("\nEnrichment complete.")

# ── Show top 15 ───────────────────────────────────────────────────────────────
r = sb.table("companies").select(
    "name,asrs_group,score_overall,score_target_gap,score_risk,target_classification,sbti_status,relationship_status,top_signal,nger_scope1_tco2e,safeguard_covered"
).order("score_overall", desc=True).limit(15).execute()

print(f"\n{'Score':<6} {'Company':<40} {'Group':<12} {'S1 (Mt)':<10} {'SF':<4} {'Rel':<14} {'Top Signal'}")
print("-" * 120)
for c in r.data:
    s1 = f"{c['nger_scope1_tco2e']/1e6:.2f}" if c.get('nger_scope1_tco2e') else "—"
    sf = "Y" if c.get('safeguard_covered') else ""
    rel = c['relationship_status'] or 'none'
    sig = (c.get('top_signal') or '—')[:40]
    print(f"{c['score_overall']:<6.1f} {c['name'][:38]:40} {c['asrs_group']:<12} {s1:<10} {sf:<4} {rel:<14} {sig}")
