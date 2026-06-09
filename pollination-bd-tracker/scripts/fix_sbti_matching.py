"""
Two jobs:
1. Fix SBTi name matching for AU companies already in the DB
   (Brambles, Transurban, Goodman, Dexus etc. — name case/suffix mismatch)
2. Insert genuinely private AU SBTi companies not in ASX universe
   (Allens, Ausgrid, Australia Post, NBN Co, NSW Ports etc.)

Run after enrich_database.py.
Usage: py scripts/fix_sbti_matching.py
"""
from __future__ import annotations
import os, re, math
from pathlib import Path
from datetime import date
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "data"

for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

# ── Name normalisation ────────────────────────────────────────────────────────
_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|berhad|bhd|group|"
    r"holdings|holding|company|co\b|plc|pte|sdn|tbk|the|and|australia|"
    r"australian|pty|metals|energy|resources|services|operations|finance)\b", re.I
)
def nkey(n: str) -> str:
    n = re.sub(r"[^a-z0-9 ]", " ", str(n).lower())
    n = _STRIP.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

def similar(a: str, b: str) -> bool:
    if not a or not b: return False
    if a == b: return True
    # Both at least 4 chars, share first 5 chars
    short = min(len(a), len(b))
    if short >= 5 and a[:5] == b[:5]: return True
    # Word overlap — at least 2 significant words in common
    wa, wb = set(a.split()), set(b.split())
    common = wa & wb
    if len(common) >= 2: return True
    if len(common) >= 1 and short <= 6: return True
    return False

# ── Load SBTi AU companies ────────────────────────────────────────────────────
sbti_raw = pd.read_excel(DATA / "sbti_companies.xlsx")
sbti_au = sbti_raw[sbti_raw["location"] == "Australia"].copy()
print(f"AU SBTi companies: {len(sbti_au)}")

# ── Load all DB companies ─────────────────────────────────────────────────────
print("Loading DB companies...")
all_db = []
offset = 0
while True:
    r = sb.table("companies").select("id,name,sbti_status,sbti_date_updated,asrs_group,sector").range(offset, offset+999).execute()
    all_db.extend(r.data)
    if len(r.data) < 1000: break
    offset += 1000
print(f"DB companies: {len(all_db)}")

db_by_key = {nkey(c["name"]): c for c in all_db}
db_ids_updated = set()

# ── Job 1: Fix name matching for companies already in DB ─────────────────────
print("\n=== Job 1: Fix SBTi matching for existing DB companies ===")
updates = []
sbti_matched_to_db = set()

for _, srow in sbti_au.iterrows():
    sname = str(srow["company_name"])
    sk = nkey(sname)
    sbti_status = str(srow.get("near_term_status") or "")
    sbti_date = str(srow["date_updated"])[:10] if pd.notna(srow.get("date_updated")) else None

    # Try exact key match first
    db_match = db_by_key.get(sk)

    # Try fuzzy match
    if not db_match:
        for dk, dc in db_by_key.items():
            if similar(sk, dk):
                db_match = dc
                break

    if db_match:
        # Only update if no SBTi status yet or status is improving
        existing_status = str(db_match.get("sbti_status") or "")
        if not existing_status or existing_status == sbti_status:
            updates.append({
                "id": db_match["id"],
                "sbti_status": sbti_status,
                "sbti_date_updated": sbti_date,
            })
            sbti_matched_to_db.add(sk)
        else:
            sbti_matched_to_db.add(sk)  # Already has data, count as matched

print(f"Matched to existing DB companies: {len(sbti_matched_to_db)}")

# Push updates
fixed = 0
for upd in updates:
    row_id = upd.pop("id")
    sb.table("companies").update(upd).eq("id", row_id).execute()
    fixed += 1
print(f"Updated: {fixed} companies with SBTi status")

# ── Job 2: Insert genuinely private companies ─────────────────────────────────
print("\n=== Job 2: Insert private AU SBTi companies not in ASX universe ===")

# Only insert companies with strategic relevance — skip tiny/unknown firms
# Criteria: well-known brand OR large sector (energy, infrastructure, finance, legal, govt)
STRATEGIC_PRIVATE = {
    "allens", "ausgrid", "australia post", "australian postal",
    "nbn co", "nbm co", "nsw ports", "port of newcastle",
    "nsw land registry", "brambles",  # Brambles may not have matched
    "investa", "frasers property", "lendlease",  # real estate
    "transurban",  # should be in ASX but just in case
    "ghd", "aurecon", "arup",  # engineering
    "king wood mallesons", "king & wood",
    "ventia", "broadspectrum",
}

# Size proxy for ASRS group — these are all large organisations
PRIVATE_SIZE_GROUP = {
    "allens": "Group 1",
    "ausgrid": "Group 1",
    "australia post": "Group 1",
    "australian postal": "Group 1",
    "nbn co": "Group 1",
    "nsw ports": "Group 2",
    "port of newcastle": "Group 2",
    "nsw land registry": "Group 2",
    "investa": "Group 1",
    "frasers property": "Group 1",
    "lendlease": "Group 1",
    "transurban": "Group 1",
    "ghd": "Group 2",
    "king wood mallesons": "Group 1",
    "king & wood": "Group 1",
    "ventia": "Group 1",
}

# SECTOR MAP from SBTi industry labels
SECTOR_MAP = {
    "Financial Services": "Financials",
    "Professional Services": "Industrials",
    "Technology": "Information Technology",
    "Construction": "Industrials",
    "Transport": "Industrials",
    "Electric Utilities": "Utilities",
    "Real Estate": "Real Estate",
    "Health Care": "Health Care",
    "Retail": "Consumer Discretionary",
    "Food, Beverage & Agriculture": "Consumer Staples",
    "Telecommunications": "Communication Services",
}

import json
cfg = json.loads((ROOT / "scoring.config.json").read_text())

def score_for_insert(asrs_group: str, sbti_status: str, sbti_date: str | None) -> dict:
    sa = float(cfg["asrs_urgency"].get(asrs_group, 1))
    # Target gap for old validated = 4, recent = 3, committed = 3
    if "removed" in str(sbti_status).lower():
        stg = 5.0
    elif sbti_date and str(sbti_date)[:4] < "2023":
        stg = 4.0
    elif sbti_date and str(sbti_date)[:4] < "2025":
        stg = 3.0
    else:
        stg = 1.0 if "targets set" in str(sbti_status).lower() else 3.0
    sr = 1.0
    si = 1.0
    srel = 1.0
    w = cfg.get("weights", {"asrs_urgency":0.25,"target_gap":0.30,"risk_signals":0.25,"intent_signals":0.10,"relationship":0.10})
    overall = round(sa*w["asrs_urgency"] + stg*w["target_gap"] + sr*w["risk_signals"] + si*w["intent_signals"] + srel*w["relationship"], 2)
    return {"score_asrs": sa, "score_target_gap": stg, "score_risk": sr, "score_intent": si, "score_relationship": srel, "score_overall": overall}

inserted = 0
skipped_small = 0
skipped_exists = 0

for _, srow in sbti_au.iterrows():
    sname = str(srow["company_name"])
    sk = nkey(sname)

    # Skip if already matched
    if sk in sbti_matched_to_db:
        skipped_exists += 1
        continue

    # Check strategic relevance
    is_strategic = any(kw in sk for kw in STRATEGIC_PRIVATE)
    # Also include any company with >500 employees implied by sector
    sbti_sector = str(srow.get("sector") or "")
    large_sectors = ["Electric Utilities", "Construction", "Transport", "Telecommunications", "Financial Services"]
    is_large_sector = any(s.lower() in sbti_sector.lower() for s in large_sectors)

    if not is_strategic and not is_large_sector:
        # Skip tiny consultancies, small retailers etc.
        if len(sname) < 30 and not any(x in sname.lower() for x in ["bank", "port", "energy", "utility", "infrastructure", "telecoms"]):
            skipped_small += 1
            continue

    # Get ASRS group
    asrs_grp = "Unclassified"
    for kw, grp in PRIVATE_SIZE_GROUP.items():
        if kw in sk:
            asrs_grp = grp
            break
    if asrs_grp == "Unclassified":
        if is_large_sector: asrs_grp = "Group 2"

    sbti_status = str(srow.get("near_term_status") or "")
    sbti_date = str(srow["date_updated"])[:10] if pd.notna(srow.get("date_updated")) else None
    sector = SECTOR_MAP.get(sbti_sector, sbti_sector or None)

    # Top signal
    if "removed" in sbti_status.lower():
        top_sig = "SBTi commitment removed — re-engagement opportunity"
    elif sbti_date and sbti_date[:4] < "2023":
        top_sig = f"SBTi validated {sbti_date[:4]} — V2 standard requires resubmission"
    elif "committed" in sbti_status.lower():
        top_sig = "SBTi committed — 24-month validation clock ticking"
    else:
        top_sig = "SBTi validated — monitor for V2 reset"

    scores = score_for_insert(asrs_grp, sbti_status, sbti_date)

    record = {
        "name": sname,
        "sector": sector,
        "is_listed": False,
        "is_private": True,
        "asrs_group": asrs_grp,
        "sbti_status": sbti_status,
        "sbti_date_updated": sbti_date,
        "target_classification": "Targets set" if "targets set" in sbti_status.lower() else (
            "SBTi committed" if "committed" in sbti_status.lower() else "No public target"
        ),
        "relationship_status": "none",
        "top_signal": top_sig,
        **scores,
    }
    # Clean nulls
    clean = {k: v for k, v in record.items() if v is not None}

    try:
        sb.table("companies").insert(clean).execute()
        inserted += 1
        print(f"  + {sname[:50]} ({asrs_grp}, {sbti_status}, {sbti_date})")
    except Exception as e:
        print(f"  ! Failed {sname}: {e}")

print(f"\nSummary:")
print(f"  Updated existing: {fixed}")
print(f"  Inserted private: {inserted}")
print(f"  Skipped (already matched): {skipped_exists}")
print(f"  Skipped (too small): {skipped_small}")

# ── Verify ────────────────────────────────────────────────────────────────────
print("\n=== Pre-2023 SBTi validated companies (V2 refresh needed) ===")
r = sb.table("companies").select("name,sbti_date_updated,asrs_group,sector,score_overall") \
    .eq("sbti_status", "Targets set") \
    .lt("sbti_date_updated", "2023-01-01") \
    .order("sbti_date_updated", desc=False) \
    .execute()
print(f"Count: {len(r.data)}")
for c in r.data:
    print(f"  {c['sbti_date_updated'][:7]}  {c['name'][:45]:47} {c['asrs_group']:12} {c['score_overall']:.1f}")
