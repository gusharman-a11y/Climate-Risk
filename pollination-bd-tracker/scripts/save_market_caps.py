"""
Read the ASX market cap workflow results and:
1. Save to data/asx_market_caps.csv
2. Update all companies in Supabase with correct ASRS group based on market cap + index
"""
import json, os, re, math
from pathlib import Path
import pandas as pd

WORKFLOW_OUTPUT = Path(r'C:\Users\ANGUS~1.HAR\AppData\Local\Temp\claude\C--Users-angus-harman\8afa0a21-674f-4471-a1f3-e99bd6ccb3ec\tasks\w9ihrpb7i.output')
ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / 'data'

# ── Read workflow result ───────────────────────────────────────────────────────
raw = WORKFLOW_OUTPUT.read_text(encoding='utf-8')
result = json.loads(raw)

# Handle both string and dict result
if isinstance(result, str):
    result = json.loads(result)

# Result is nested under 'result' key
if 'result' in result:
    result = result['result']
classified = result.get('classified', [])
if not classified and isinstance(result, list):
    classified = result

print(f'Companies from workflow: {len(classified)}')

# ── Build DataFrame ───────────────────────────────────────────────────────────
df = pd.DataFrame(classified)
df = df[df['asx_code'].notna() & (df['asx_code'] != '')]
df['asx_code'] = df['asx_code'].str.upper().str.strip()
df = df.drop_duplicates(subset='asx_code', keep='first')

# Summary
print('\nASRS group distribution:')
print(df['asrs_group'].value_counts().to_string())
print(f'\nWith market cap: {df["market_cap_aud"].notna().sum()}')
print(f'Without market cap: {df["market_cap_aud"].isna().sum()}')

# Save CSV
csv_path = DATA / 'asx_market_caps.csv'
df.to_csv(csv_path, index=False)
print(f'\nSaved {len(df)} companies to {csv_path}')

# Show sample
print('\nTop 10 by market cap:')
print(df.nlargest(10, 'market_cap_aud')[['asx_code','name','market_cap_aud','index_membership','asrs_group']].to_string())

# ── Update Supabase ────────────────────────────────────────────────────────────
for line in (ROOT / '.env.local').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

print('\nLoading DB companies...')
all_db = []
offset = 0
while True:
    r = sb.table('companies').select('id,name,asx_code,asrs_group').range(offset, offset+999).execute()
    all_db.extend(r.data)
    if len(r.data) < 1000: break
    offset += 1000
print(f'DB companies: {len(all_db)}')

# Build ASX code lookup from workflow data
asx_lookup = {row['asx_code']: dict(row) for _, row in df.iterrows()}

updated = 0
reclassified = 0
for company in all_db:
    asx_code = str(company.get('asx_code') or '').upper().strip()
    if not asx_code:
        continue

    mc_data = asx_lookup.get(asx_code)
    if not mc_data:
        continue

    new_group = mc_data.get('asrs_group', 'Unclassified')
    old_group = company.get('asrs_group', 'Unclassified')

    if new_group != old_group and new_group != 'Unclassified':
        mc = mc_data.get('market_cap_aud')
        patch = {
            'asrs_group': new_group,
            'market_cap_tier': mc_data.get('index_membership', ''),
        }
        if mc:
            patch['revenue_aud'] = None  # Don't overwrite revenue with market cap

        sb.table('companies').update(patch).eq('id', company['id']).execute()
        reclassified += 1
        if reclassified <= 10:
            print(f'  {asx_code}: {old_group} -> {new_group} (mkt cap: {mc_data.get("market_cap_aud")})')

    updated += 1

print(f'\nMatched: {updated} companies by ASX code')
print(f'Reclassified: {reclassified} companies')

# Final distribution
print('\nVerifying DB group distribution...')
r = sb.table('companies').select('asrs_group').execute()
from collections import Counter
counts = Counter(c['asrs_group'] for c in r.data)
for k, v in sorted(counts.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
