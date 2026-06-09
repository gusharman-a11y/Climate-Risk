"""
Backfill sbti_target_text from the SBTi companies database.
Run after adding the column in Supabase.
Usage: py scripts/backfill_sbti_text.py
"""
import os, re
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).parent.parent
DATA = ROOT.parent / 'data'

for line in (ROOT / '.env.local').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

_STRIP = re.compile(
    r'\b(?:corporation|corp|incorporated|inc|limited|ltd|group|holdings|holding|'
    r'company|co\b|plc|pte|australia|australian|pty|metals|energy|resources)\b', re.I
)
def nkey(n):
    n = re.sub(r'[^a-z0-9 ]', ' ', str(n).lower())
    n = _STRIP.sub('', n)
    return re.sub(r'\s+', ' ', n).strip()

# Load SBTi data with target text
sbti = pd.read_excel(DATA / 'sbti_companies.xlsx')
au = sbti[sbti['location'] == 'Australia'].copy()
sbti_map = {}
for _, row in au.iterrows():
    k = nkey(str(row['company_name']))
    text = str(row.get('full_target_language') or '').strip()
    classification = str(row.get('near_term_target_classification') or '').strip()
    target_year = str(row.get('near_term_target_year') or '').strip()
    if text and text != 'nan':
        sbti_map[k] = {'text': text[:1000], 'classification': classification, 'year': target_year}

print(f'SBTi AU companies with target text: {len(sbti_map)}')

# Load DB companies
print('Loading DB companies...')
all_db = []
offset = 0
while True:
    r = sb.table('companies').select('id,name,sbti_status').range(offset, offset+999).execute()
    all_db.extend(r.data)
    if len(r.data) < 1000: break
    offset += 1000
print(f'DB companies: {len(all_db)}')

updated = 0
for company in all_db:
    nk = nkey(str(company['name']))
    data = sbti_map.get(nk)
    if not data:
        # Fuzzy match
        for sk, sd in sbti_map.items():
            if sk and nk and len(nk) >= 4 and (sk.startswith(nk[:min(6,len(nk))]) or nk.startswith(sk[:min(6,len(sk))])):
                data = sd
                break
    if data and data['text']:
        sb.table('companies').update({'sbti_target_text': data['text']}).eq('id', company['id']).execute()
        updated += 1
        if updated <= 5:
            print(f"  {company['name'][:40]:42} -> {data['text'][:80]}...")

print(f'\nUpdated: {updated} companies with SBTi target text')
