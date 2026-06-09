"""
Rescore all companies using scoring.config.json weights.
Run this whenever you edit the config or want to refresh scores.

Usage:
  py scripts/rescore.py
"""
from __future__ import annotations
import os, json, math
from pathlib import Path
from datetime import date

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "data"

# Load env
for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

import re
import pandas as pd

from supabase import create_client
sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# Load config
cfg = json.loads((ROOT / "scoring.config.json").read_text())

# Build ASX200 name keys → Group 1 override
_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|group|"
    r"holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|australia|australian|pty)\b", re.I
)
def _nkey(n):
    n = re.sub(r"[^a-z0-9 ]", " ", str(n).lower())
    n = _STRIP.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

asx200_df = pd.read_csv(DATA / "asx200_non_sbti.csv")
ASX200_KEYS = {_nkey(n) for n in asx200_df["Company Name"]}
NGER_DF = pd.read_csv(DATA / "nger_targets.csv")
NGER_KEYS = {_nkey(n) for n in NGER_DF["NGER Reporting Entity"]}

size_df = pd.read_csv(DATA / "company_size.csv")
SIZE_LOOKUP = {_nkey(r["Company Name"]): dict(r) for _, r in size_df.iterrows()}

MC_TIER_TO_GROUP = {"mega": "Group 1", "large": "Group 1", "mid": "Group 2", "small": "Group 3", "micro": "Group 3"}

# ASX full listing for market cap tier lookup
asx_full = pd.read_csv(DATA / "ASXListedCompanies.csv", skiprows=1)
asx_full.columns = ["name", "asx_code", "sector"]

def classify_asrs(row: dict) -> str:
    existing = row.get("asrs_group", "")
    if existing in ("Group 1", "Group 2", "Group 3"):
        return existing

    nk = _nkey(row.get("name", ""))

    # 1. Use actual financial data if available
    size = SIZE_LOOKUP.get(nk)
    if not size:
        for k, v in SIZE_LOOKUP.items():
            if k and nk and (k == nk or k.startswith(nk[:6]) or nk.startswith(k[:6])):
                size = v; break
    if size:
        rev = float(size.get("Revenue (AUD)") or 0)
        ast = float(size.get("Assets (AUD)") or 0)
        emp = float(size.get("Employees") or 0)
        g1 = (rev >= 500e6) + (ast >= 1e9) + (emp >= 500)
        if g1 >= 2: return "Group 1"
        g2 = (rev >= 200e6) + (ast >= 500e6) + (emp >= 250)
        if g2 >= 2: return "Group 2"
        return "Group 3"

    # 2. ASX200 membership = Group 1
    if nk in ASX200_KEYS:
        return "Group 1"
    for k in ASX200_KEYS:
        if k and nk and len(nk) >= 4 and k.startswith(nk[:4]):
            return "Group 1"

    # 3. NGER reporter = Group 2 minimum
    if nk in NGER_KEYS:
        return "Group 2"
    for k in NGER_KEYS:
        if k and nk and len(nk) >= 5 and k.startswith(nk[:5]):
            return "Group 2"

    # 4. Market cap tier from DB
    mc = str(row.get("market_cap_tier") or "").lower().strip()
    if mc in MC_TIER_TO_GROUP:
        return MC_TIER_TO_GROUP[mc]

    return existing or "Unclassified"

def score_asrs(group: str) -> float:
    return float(cfg["asrs_urgency"].get(group, 1))

def score_target_gap(sbti_status: str, target_class: str, sbti_date: str | None) -> float:
    s = str(sbti_status or "").lower()
    tc = str(target_class or "").strip()
    tg = cfg["target_gap"]

    if "removed" in s:
        return float(tg.get("sbti_removed", 5))
    if tc in tg:
        val = tg[tc]
        # Extra: SBTi vintage check
        if tc == "Targets set" and sbti_date:
            try:
                yr = int(str(sbti_date)[:4])
                if yr < 2023:
                    return float(tg.get("sbti_pre_2023", 4))
                if yr < 2025:
                    return float(tg.get("sbti_2023_2024", 3))
            except Exception:
                pass
        return float(val)
    if "committed" in s:
        return float(tg.get("SBTi committed", 3))
    return float(tg.get("No public target", 5))

def score_risk(safeguard: bool, sbti_status: str, target_year) -> float:
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
    return score

def score_intent(nzt_plan, nzt_r2z) -> float:
    si = cfg["intent_signals"]
    score = float(si.get("default", 1))
    if nzt_r2z:
        score = max(score, float(si.get("race_to_zero_member", 3)))
    if nzt_plan:
        score = max(score, float(si.get("nzt_published_plan", 2)))
    return score

def score_relationship(rel: str) -> float:
    return float(cfg["relationship"].get(rel or "none", 1))

def top_signal(sa, stg, sr, si, srel, row) -> str:
    signals = []
    tc = row.get("target_classification", "")
    sbti_s = str(row.get("sbti_status") or "").lower()

    if "removed" in sbti_s:
        signals.append("SBTi commitment removed — re-engagement")
    elif stg >= 4:
        signals.append(f"No credible target ({tc})" if tc else "No public target")
    if row.get("safeguard_covered"):
        signals.append("Safeguard covered facility")
    if sa >= 5:
        signals.append("ASRS Group 1 — mandatory NOW")
    elif sa >= 4:
        signals.append("ASRS Group 2 — mandatory FY2026/27")
    if srel >= 4:
        signals.append("Past client — re-engagement opportunity")
    elif srel >= 3:
        signals.append("Warm contact — lower conversion cost")
    return signals[0] if signals else "ASRS reporting obligation"

# Load all companies
print("Loading companies from Supabase...")
BATCH = 1000
all_companies = []
offset = 0
while True:
    r = sb.table("companies").select(
        "id,name,asrs_group,market_cap_tier,sbti_status,sbti_date_updated,target_classification,target_year,"
        "safeguard_covered,nzt_published_plan,nzt_race_to_zero,relationship_status"
    ).range(offset, offset + BATCH - 1).execute()
    all_companies.extend(r.data)
    if len(r.data) < BATCH:
        break
    offset += BATCH

print(f"Rescoring {len(all_companies)} companies...")

updates = []
for row in all_companies:
    row["asrs_group"] = classify_asrs(row)
    sa   = score_asrs(row.get("asrs_group", ""))
    stg  = score_target_gap(row.get("sbti_status", ""), row.get("target_classification", ""), row.get("sbti_date_updated"))
    sr   = score_risk(row.get("safeguard_covered", False), row.get("sbti_status", ""), row.get("target_year"))
    si   = score_intent(row.get("nzt_published_plan"), row.get("nzt_race_to_zero"))
    srel = score_relationship(row.get("relationship_status", "none"))
    overall = round((sa + stg + sr + si + srel) / 5, 2)
    sig = top_signal(sa, stg, sr, si, srel, row)

    updates.append({
        "id": row["id"],
        "asrs_group": row["asrs_group"],
        "score_asrs": sa,
        "score_target_gap": stg,
        "score_risk": sr,
        "score_intent": si,
        "score_relationship": srel,
        "score_overall": overall,
        "top_signal": sig,
    })

# Push updates one at a time (Supabase REST doesn't support bulk update by id)
for i, upd in enumerate(updates):
    row_id = upd.pop("id")
    sb.table("companies").update(upd).eq("id", row_id).execute()
    if (i + 1) % 100 == 0:
        print(f"  Updated {i+1}/{len(updates)}")

print("\nRescore complete.")

# Show top 10
r = sb.table("companies").select(
    "name,asrs_group,score_overall,score_target_gap,target_classification,relationship_status,top_signal"
).order("score_overall", desc=True).limit(10).execute()

print(f"\n{'Score':<6} {'Company':<42} {'Group':<12} {'Target':<28} {'Rel'}")
print("-" * 110)
for c in r.data:
    print(f"{c['score_overall']:<6.1f} {c['name'][:40]:<42} {c['asrs_group']:<12} {(c.get('target_classification') or '—')[:26]:<28} {c['relationship_status']}")
