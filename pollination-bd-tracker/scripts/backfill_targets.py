"""
Backfill target_description and target_scope from ASX200 research data.
Run once after adding the columns in Supabase.

Usage: py scripts/backfill_targets.py
"""
import os, re, math
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "data"

for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|group|holdings|holding|"
    r"company|co\b|plc|pte|australia|australian|pty|metals|energy|resources)\b", re.I
)
def nkey(n):
    n = re.sub(r"[^a-z0-9 ]", " ", str(n).lower())
    n = _STRIP.sub("", n)
    return re.sub(r"\s+", " ", n).strip()

# Load ASX200 research — has Stated Target Description
asx200 = pd.read_csv(DATA / "asx200_non_sbti.csv")
target_lookup = {}
for _, row in asx200.iterrows():
    k = nkey(str(row["Company Name"]))
    desc = str(row.get("Stated Target Description", "") or "").strip()
    if desc and desc != "nan":
        target_lookup[k] = desc

# Load NGER targets — also has target descriptions
nger = pd.read_csv(DATA / "nger_targets.csv")
for _, row in nger.iterrows():
    k = nkey(str(row["NGER Reporting Entity"]))
    if k not in target_lookup:
        desc = str(row.get("Stated Target Description", "") or "").strip()
        if desc and desc != "nan":
            target_lookup[k] = desc

print(f"Target descriptions available: {len(target_lookup)}")

# Scope inference from description text
def infer_scope(desc: str) -> str | None:
    d = desc.lower()
    parts = []
    if "scope 1" in d or "s1" in d:
        parts.append("Scope 1")
    if "scope 2" in d or "s2" in d:
        parts.append("Scope 2")
    if "scope 3" in d or "s3" in d:
        parts.append("Scope 3")
    if "all scope" in d or "scope 1, 2 and 3" in d or "scope 1,2,3" in d:
        return "Scope 1, 2 & 3"
    if parts:
        return " & ".join(parts)
    if "net zero" in d and "scope 3" not in d:
        return "Scope 1 & 2 (operational)"
    return None

# Load all companies from Supabase
print("Loading companies...")
all_companies = []
offset = 0
while True:
    r = sb.table("companies").select("id,name").range(offset, offset + 999).execute()
    all_companies.extend(r.data)
    if len(r.data) < 1000:
        break
    offset += 1000

print(f"Total: {len(all_companies)} companies")

updates = []
matched = 0
for row in all_companies:
    k = nkey(str(row["name"]))
    desc = target_lookup.get(k)
    if not desc:
        # Try prefix match
        for tk, td in target_lookup.items():
            if tk and k and len(k) >= 4 and (k.startswith(tk[:min(6,len(tk))]) or tk.startswith(k[:min(6,len(k))])):
                desc = td
                break
    if desc:
        scope = infer_scope(desc)
        updates.append({"id": row["id"], "target_description": desc[:500], "target_scope": scope})
        matched += 1

print(f"Matched: {matched} companies with target descriptions")

# Push
for i, upd in enumerate(updates):
    row_id = upd.pop("id")
    sb.table("companies").update(upd).eq("id", row_id).execute()
    if (i + 1) % 50 == 0:
        print(f"  {i+1}/{len(updates)}")

print(f"\nDone. {matched} companies updated with target descriptions.")

# Verify Fortescue
r = sb.table("companies").select("name,target_description,target_scope,net_zero_year,nzt_end_year").ilike("name", "%fortescue%").execute()
for c in r.data:
    print(f"\nFortescue check:")
    print(f"  target_description: {c.get('target_description')}")
    print(f"  target_scope: {c.get('target_scope')}")
    print(f"  net_zero_year (from research): {c.get('net_zero_year')}")
    print(f"  nzt_end_year (NZT, more accurate): {c.get('nzt_end_year')}")
