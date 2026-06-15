"""Diagnose SBTi matching and scoring for validated companies."""
import os, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / "data"

for line in (ROOT / ".env.local").read_text(encoding="utf-8").splitlines():
    if "=" in line and not line.startswith("#"):
        k, v = line.split("=", 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ["NEXT_PUBLIC_SUPABASE_URL"], os.environ["SUPABASE_SECRET_KEY"])

_STRIP = re.compile(
    r"\b(?:corporation|corp|incorporated|inc|limited|ltd|group|holdings|holding|"
    r"company|co\b|plc|pte|australia|australian|pty)\b", re.I
)
def nkey(n):
    n = re.sub(r"[^a-z0-9 ]", " ", str(n).lower())
    n = _STRIP.sub("", n); return re.sub(r"\s+", " ", n).strip()

# Check how many DB companies have Targets set
print("=== DB companies with SBTi Targets set ===")
r = sb.table("companies").select(
    "name,sbti_status,sbti_date_updated,score_overall,asrs_group"
).eq("sbti_status", "Targets set").order("score_overall", desc=True).execute()
print(f"Count: {len(r.data)}")
for c in r.data[:15]:
    print(f"  {c['score_overall']:.1f}  {c['name'][:40]:42} {c['asrs_group']:12} {c['sbti_date_updated']}")

print()
print("=== Why validated companies score low ===")
print("A pre-2023 validated company (Group 1):")
print("  ASRS=5x0.25=1.25 + TargetGap=4x0.30=1.20 + Risk=1x0.25=0.25 + Intent=1x0.10=0.10 + Rel=1x0.10=0.10 = 2.90")
print("A SBTi-removed company (Group 1):")
print("  ASRS=5x0.25=1.25 + TargetGap=5x0.30=1.50 + Risk=5x0.25=1.25 + Intent=1x0.10=0.10 + Rel=1x0.10=0.10 = 4.20")
print("=> Validated companies BURIED under no-target companies. Need a separate section.")

print()
print("=== SBTi AU companies NOT matched in DB ===")
sbti_raw = pd.read_excel(DATA / "sbti_companies.xlsx")
sbti_au = sbti_raw[sbti_raw["location"] == "Australia"].copy()
db_names = {nkey(c["name"]) for c in sb.table("companies").select("name").execute().data}
unmatched = []
for _, row in sbti_au.iterrows():
    k = nkey(str(row["company_name"]))
    if k not in db_names:
        unmatched.append(f"  {row['near_term_status']:20} {row['company_name']}")
print(f"Unmatched: {len(unmatched)} of {len(sbti_au)}")
for u in unmatched[:20]: print(u)
