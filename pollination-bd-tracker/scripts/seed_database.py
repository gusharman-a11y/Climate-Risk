"""
Seed the Pollination BD Tracker Supabase database.

Merges:
  - data/ASXListedCompanies.csv          — full ASX universe
  - data/asx200_non_sbti.csv             — ASX200 with target research
  - data/nger_targets.csv                — NGER large emitters with targets
  - data/nzt_snapshot.xlsx               — Net Zero Tracker AU companies
  - data/sbti_companies.xlsx             — SBTi global database (AU filtered)
  - Downloads/Pollination_BD_Tracker_June2026.xlsx — existing relationships/pipeline

Usage:
  pip install pandas openpyxl supabase python-dotenv
  python scripts/seed_database.py

Env vars needed (.env.local):
  NEXT_PUBLIC_SUPABASE_URL
  NEXT_PUBLIC_SUPABASE_ANON_KEY
"""

from __future__ import annotations

import os
import re
import sys
import math
from pathlib import Path
from datetime import date

import pandas as pd

ROOT = Path(__file__).parent.parent          # pollination-bd-tracker/
DATA = ROOT.parent / "data"                  # Climate-Risk/data/

# ── Load .env.local ───────────────────────────────────────────────────────────
env_path = ROOT / ".env.local"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            os.environ.setdefault(k.strip(), v.strip())

SUPABASE_URL = os.environ.get("NEXT_PUBLIC_SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("NEXT_PUBLIC_SUPABASE_ANON_KEY", "")

if not SUPABASE_URL or not SUPABASE_KEY:
    print("ERROR: Set NEXT_PUBLIC_SUPABASE_URL and SUPABASE_SECRET_KEY in .env.local")
    sys.exit(1)

from supabase import create_client  # noqa: E402
sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── Name normalisation ────────────────────────────────────────────────────────
_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|group|"
    r"holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|australia|australian|pty)\b",
    re.I,
)

def _nkey(name: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(name).lower())
    n = _STRIP.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

def _match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    ta, tb = a.split(), b.split()
    if not ta or not tb:
        return False
    if ta[0] == tb[0] and len(set(ta) & set(tb)) >= min(2, len(ta)):
        return True
    return (len(a) >= 6 and b.startswith(a[:6])) or (len(b) >= 6 and a.startswith(b[:6]))

# ── ASRS group helper ─────────────────────────────────────────────────────────
MC_TO_GROUP = {"mega": "Group 1", "large": "Group 1", "mid": "Group 2", "small": "Group 3", "micro": "Group 3"}

def asrs_group(row: dict) -> str:
    rev = float(row.get("revenue_aud") or 0)
    ast = float(row.get("assets_aud") or 0)
    emp = float(row.get("employee_count") or 0)
    hits_g1 = (rev >= 500e6) + (ast >= 1e9) + (emp >= 500)
    if hits_g1 >= 2:
        return "Group 1"
    hits_g2 = (rev >= 200e6) + (ast >= 500e6) + (emp >= 250)
    if hits_g2 >= 2:
        return "Group 2"
    hits_g3 = (rev >= 50e6) + (ast >= 25e6) + (emp >= 100)
    if hits_g3 >= 2:
        return "Group 3"
    mc = str(row.get("market_cap_tier") or "").strip().lower()
    return MC_TO_GROUP.get(mc, "Unclassified")

# ── Scoring engine ─────────────────────────────────────────────────────────────
def score_asrs(group: str) -> float:
    return {"Group 1": 5, "Group 2": 4, "Group 3": 2, "Unclassified": 1}.get(group, 1)

def score_target_gap(sbti_status: str, target_class: str, sbti_date: str | None) -> float:
    s = str(sbti_status or "").strip().lower()
    tc = str(target_class or "").strip()
    if "removed" in s:
        return 5
    if tc == "No public target":
        return 5
    if tc in ("Aspirational", "Net-zero only"):
        return 4
    # SBTi vintage check — pre-2023 needs V2 refresh
    if "targets set" in s or tc == "Targets set":
        if sbti_date:
            try:
                yr = int(str(sbti_date)[:4])
                if yr < 2023:
                    return 4  # old validation — V2 refresh needed
                if yr < 2025:
                    return 3  # scope 3 methodology risk
                return 1
            except Exception:
                pass
        return 2
    if tc == "Quantitative non-validated":
        return 2
    if "committed" in s:
        return 3
    return 3

def score_risk(safeguard: bool, sbti_status: str, target_year: int | None) -> float:
    s = str(sbti_status or "").strip().lower()
    score = 1
    if safeguard:
        score = max(score, 3)
    if "removed" in s:
        score = max(score, 4)
    if target_year and (target_year - date.today().year) <= 2:
        score = max(score, 3)
    return float(score)

def score_intent(nzt_published: bool | None, nzt_r2z: bool | None) -> float:
    score = 1
    if nzt_r2z:
        score = max(score, 2)
    if nzt_published:
        score = max(score, 2)
    return float(score)

def score_relationship(rel_status: str) -> float:
    return {"current_client": 0, "past_client": 4, "warm_contact": 3, "none": 1}.get(rel_status, 1)

def compute_scores(row: dict) -> dict:
    sa = score_asrs(row.get("asrs_group", ""))
    stg = score_target_gap(row.get("sbti_status", ""), row.get("target_classification", ""), row.get("sbti_date_updated"))
    sr = score_risk(row.get("safeguard_covered", False), row.get("sbti_status", ""), row.get("target_year"))
    si = score_intent(row.get("nzt_published_plan"), row.get("nzt_race_to_zero"))
    srel = score_relationship(row.get("relationship_status", "none"))
    overall = round((sa + stg + sr + si + srel) / 5, 2)

    # Top signal text
    signals = []
    if stg >= 4:
        tc = row.get("target_classification", "")
        signals.append(f"No credible target ({tc})" if tc else "No public target")
    if "removed" in str(row.get("sbti_status", "")).lower():
        signals.append("SBTi commitment removed")
    if row.get("safeguard_covered"):
        signals.append("Safeguard covered facility")
    if row.get("asrs_group") == "Group 1":
        signals.append("ASRS mandatory NOW (Group 1)")

    return {
        "score_asrs": sa,
        "score_target_gap": stg,
        "score_risk": sr,
        "score_intent": si,
        "score_relationship": srel,
        "score_overall": overall,
        "top_signal": signals[0] if signals else None,
    }

# ── Load data sources ──────────────────────────────────────────────────────────
print("Loading data sources…")

# 1. ASX full universe
asx_raw = pd.read_csv(DATA / "ASXListedCompanies.csv", skiprows=1)
asx_raw.columns = ["name", "asx_code", "sector"]
asx_raw["is_listed"] = True

# 2. ASX200 with target research
asx200 = pd.read_csv(DATA / "asx200_non_sbti.csv")
asx200_keys = {_nkey(n): row for n, row in zip(asx200["Company Name"], asx200.to_dict("records"))}

# 3. NGER large emitters
nger = pd.read_csv(DATA / "nger_targets.csv")
nger_keys = {_nkey(n): row for n, row in zip(nger["NGER Reporting Entity"], nger.to_dict("records"))}

# 4. SBTi AU companies
sbti_all = pd.read_excel(DATA / "sbti_companies.xlsx")
sbti_au = sbti_all[sbti_all["location"] == "Australia"].copy()
sbti_keys = {_nkey(n): row for n, row in zip(sbti_au["company_name"], sbti_au.to_dict("records"))}

# 5. NZT AU companies
nzt = pd.read_excel(DATA / "nzt_snapshot.xlsx", header=1, sheet_name="Current Snapshot")
nzt.columns = [str(c).strip() for c in nzt.columns]
nzt_au = nzt[(nzt["Country"].astype(str).str.upper() == "AUS") &
             (nzt["Entity_type"].astype(str).str.lower() == "company")].copy()
nzt_keys = {_nkey(n): row for n, row in zip(nzt_au["Name"], nzt_au.to_dict("records"))}

# 6. BD Tracker Excel (relationships + pipeline)
bd_file = Path.home() / "Downloads" / "Pollination_BD_Tracker_June2026.xlsx"
active_proposals: set[str] = set()
pipeline_map: dict[str, dict] = {}
strategic_owners: dict[str, str] = {}

if bd_file.exists():
    xl = pd.ExcelFile(bd_file)
    ap = xl.parse("Active Proposals")
    for _, r in ap.iterrows():
        if pd.notna(r.get("Client")):
            active_proposals.add(_nkey(str(r["Client"])))

    lp = xl.parse("Live Pipeline")
    STAGE_MAP = {
        "mandated / contracted": "mandated",
        "approaching negotiation": "negotiation",
        "proposals delivered": "proposal",
        "proposal preparation": "proposal",
        "qualified prospects": "qualified",
        "prospects": "prospect",
        "missed opportunities": "missed",
    }
    for _, r in lp.iterrows():
        if pd.notna(r.get("Client")):
            k = _nkey(str(r["Client"]))
            stage_raw = str(r.get("Stage", "")).lower().strip()
            pipeline_map[k] = {
                "pipeline_stage": STAGE_MAP.get(stage_raw, "prospect"),
                "pipeline_owner": str(r.get("Owner", "")) if pd.notna(r.get("Owner")) else None,
            }

    so = xl.parse("Strategic Owners")
    for _, r in so.iterrows():
        if pd.notna(r.get("Client")):
            k = _nkey(str(r["Client"]))
            strategic_owners[k] = str(r.get("Pollination Lead", ""))

print(f"  ASX companies: {len(asx_raw)}")
print(f"  ASX200 research: {len(asx200)}")
print(f"  NGER emitters: {len(nger)}")
print(f"  SBTi AU: {len(sbti_au)}")
print(f"  NZT AU companies: {len(nzt_au)}")
print(f"  Active proposals: {len(active_proposals)}")
print(f"  Pipeline entries: {len(pipeline_map)}")
print(f"  Strategic accounts: {len(strategic_owners)}")

# ── Build company records ─────────────────────────────────────────────────────
def safe(v, cast=None):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if cast:
        try:
            return cast(v)
        except Exception:
            return None
    return v

companies_out = []
seen_keys: set[str] = set()

def nzt_match(nkey: str) -> dict | None:
    if nkey in nzt_keys:
        return nzt_keys[nkey]
    for k, v in nzt_keys.items():
        if _match(nkey, k):
            return v
    return None

def sbti_match(nkey: str) -> dict | None:
    if nkey in sbti_keys:
        return sbti_keys[nkey]
    for k, v in sbti_keys.items():
        if _match(nkey, k):
            return v
    return None

def asx200_match(nkey: str) -> dict | None:
    if nkey in asx200_keys:
        return asx200_keys[nkey]
    for k, v in asx200_keys.items():
        if _match(nkey, k):
            return v
    return None

def nger_match(nkey: str) -> dict | None:
    if nkey in nger_keys:
        return nger_keys[nkey]
    for k, v in nger_keys.items():
        if _match(nkey, k):
            return v
    return None

def build_company(name: str, asx_code: str | None, sector: str | None) -> dict:
    nkey = _nkey(name)

    a200 = asx200_match(nkey)
    nger_r = nger_match(nkey)
    sbti_r = sbti_match(nkey)
    nzt_r = nzt_match(nkey)

    # Target classification — prefer ASX200 research, fall back to NZT
    tc = None
    if a200:
        tc = safe(a200.get("Target Classification"))
    if not tc and nzt_r:
        status = str(nzt_r.get("Status_of_end_target", "")).lower()
        interim = safe(nzt_r.get("Interim_target_percentage_reduction"), float)
        if "corporate strategy" in status and interim:
            tc = "Quantitative non-validated"
        elif "corporate strategy" in status:
            tc = "Net-zero only"
        elif status:
            tc = "Aspirational"
    if not tc and nger_r:
        tc = safe(nger_r.get("Target Classification"))
    if not tc:
        tc = "No public target"

    # Relationship
    rel_status = "none"
    rel_lead = None
    pipeline_stage = None
    pipeline_owner = None

    if nkey in active_proposals:
        rel_status = "current_client"
    if nkey in strategic_owners:
        rel_lead = strategic_owners[nkey]
        if rel_status == "none":
            rel_status = "warm_contact"

    pm = None
    for pk in pipeline_map:
        if pk == nkey or _match(pk, nkey):
            pm = pipeline_map[pk]
            break
    if pm:
        pipeline_stage = pm.get("pipeline_stage")
        pipeline_owner = pm.get("pipeline_owner")

    rec: dict = {
        "name": name,
        "asx_code": asx_code,
        "sector": sector or (safe(a200.get("GICS Sector")) if a200 else None),
        "industry": safe(a200.get("GICS Industry")) if a200 else None,
        "is_listed": True if asx_code else False,
        "is_private": not bool(asx_code),
        "market_cap_tier": safe(a200.get("Market Cap Tier")) if a200 else None,
        # Emissions
        "nger_scope1_tco2e": None,
        "nger_year": "FY2023-24",
        "safeguard_covered": False,
        # Target
        "sbti_status": safe(sbti_r.get("near_term_status")) if sbti_r else None,
        "sbti_date_updated": str(sbti_r.get("date_updated"))[:10] if sbti_r and pd.notna(sbti_r.get("date_updated")) else None,
        "target_classification": tc,
        "target_year": safe(a200.get("Stated Target Year"), int) if a200 else (safe(nger_r.get("Stated Target Year"), int) if nger_r else None),
        "net_zero_year": safe(a200.get("Stated Net-Zero Year"), int) if a200 else None,
        # NZT
        "nzt_end_target": safe(nzt_r.get("End_target")) if nzt_r else None,
        "nzt_end_year": safe(nzt_r.get("End_target_year"), int) if nzt_r else None,
        "nzt_status": safe(nzt_r.get("Status_of_end_target")) if nzt_r else None,
        "nzt_interim_pct": safe(nzt_r.get("Interim_target_percentage_reduction"), float) if nzt_r else None,
        "nzt_published_plan": (str(nzt_r.get("Published_plan", "")).lower() == "yes") if nzt_r else None,
        "nzt_race_to_zero": (str(nzt_r.get("Race_to_zero_member", "")).lower() == "yes") if nzt_r else None,
        # Relationship
        "relationship_status": rel_status,
        "relationship_lead": rel_lead,
        # Pipeline
        "pipeline_stage": pipeline_stage,
        "pipeline_owner": pipeline_owner,
    }

    # ASRS group
    rec["asrs_group"] = asrs_group(rec)

    # Scores
    rec.update(compute_scores(rec))

    return rec

# Process ASX universe (primary source)
for _, row in asx_raw.iterrows():
    name = str(row["name"]).strip()
    asx_code = str(row["asx_code"]).strip() if pd.notna(row.get("asx_code")) else None
    sector = str(row["sector"]).strip() if pd.notna(row.get("sector")) else None
    nkey = _nkey(name)
    if nkey in seen_keys:
        continue
    seen_keys.add(nkey)
    companies_out.append(build_company(name, asx_code, sector))

# Add NGER companies not in ASX universe
for _, row in nger.iterrows():
    name = str(row["NGER Reporting Entity"]).strip()
    nkey = _nkey(name)
    if nkey in seen_keys:
        continue
    seen_keys.add(nkey)
    rec = build_company(name, None, None)
    companies_out.append(rec)

# Add BD tracker companies not yet in universe
for client_key in list(active_proposals) + list(strategic_owners.keys()):
    if client_key in seen_keys:
        continue
    seen_keys.add(client_key)
    # Reconstruct display name from key (best effort)
    display = client_key.title()
    rec = build_company(display, None, None)
    companies_out.append(rec)

print(f"\nTotal companies to seed: {len(companies_out)}")

# ── Upsert to Supabase ────────────────────────────────────────────────────────
BATCH = 100

def clean(rec: dict) -> dict:
    """Remove None values that Supabase/JSON dislikes for non-nullable cols."""
    return {k: v for k, v in rec.items() if v is not None or k in ("asx_code",)}

print("Clearing existing data…")
sb.table("companies").delete().neq("id", "00000000-0000-0000-0000-000000000000").execute()

print("Inserting to Supabase…")
for i in range(0, len(companies_out), BATCH):
    batch = [clean(r) for r in companies_out[i:i+BATCH]]
    sb.table("companies").insert(batch).execute()
    print(f"  Batch {i//BATCH + 1}: {len(batch)} rows")

print("\nDone! Seed complete.")
print(f"  Total: {len(companies_out)} companies")
print(f"  Current clients (excluded from hot sheet): {sum(1 for c in companies_out if c['relationship_status'] == 'current_client')}")
print(f"  Strategic accounts: {sum(1 for c in companies_out if c['relationship_lead'])}")
print(f"  Pipeline entries: {sum(1 for c in companies_out if c['pipeline_stage'])}")
