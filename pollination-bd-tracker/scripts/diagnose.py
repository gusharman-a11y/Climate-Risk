import os
from pathlib import Path
from collections import Counter

for line in Path('C:/Users/angus.harman/Climate-Risk/pollination-bd-tracker/.env.local').read_text().splitlines():
    if '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

print("=== SBTi status distribution ===")
r = sb.table('companies').select('sbti_status').execute()
counts = Counter(c['sbti_status'] or 'None' for c in r.data)
for k, v in sorted(counts.items(), key=lambda x: -x[1])[:12]:
    print(f"  {v:4d}  {k}")

print()
print("=== NGER emissions coverage ===")
r2 = sb.table('companies').select('name,nger_scope1_tco2e,target_year,target_classification').not_.is_('nger_scope1_tco2e', 'null').order('nger_scope1_tco2e', desc=True).limit(15).execute()
print(f"  Companies with emissions data: {len(r2.data)}")
for c in r2.data:
    print(f"  {c['name'][:40]:42} {c['nger_scope1_tco2e']:>14,.0f} tCO2e  target_yr={c['target_year']}  {c['target_classification']}")

print()
print("=== Score distribution ===")
r3 = sb.table('companies').select('score_overall').execute()
scores = [c['score_overall'] for c in r3.data if c['score_overall']]
buckets = Counter(round(s * 2) / 2 for s in scores)
for k in sorted(buckets.keys(), reverse=True)[:10]:
    print(f"  {k:.1f}: {buckets[k]} companies")
