import os
from pathlib import Path

for line in Path('C:/Users/angus.harman/Climate-Risk/pollination-bd-tracker/.env.local').read_text().splitlines():
    if '=' in line:
        k, v = line.split('=', 1)
        os.environ[k.strip()] = v.strip()

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

r = sb.table('companies') \
    .select('name,asx_code,asrs_group,score_overall,target_classification,relationship_status,relationship_lead,top_signal') \
    .order('score_overall', desc=True) \
    .limit(20) \
    .execute()

print(f"{'Score':<6} {'Company':<42} {'Group':<12} {'Target':<28} {'Rel':<14} {'Top Signal'}")
print("-" * 130)
for c in r.data:
    rel = c['relationship_status'] or 'none'
    lead = f" ({c['relationship_lead']})" if c.get('relationship_lead') else ''
    sig = (c.get('top_signal') or '—')[:35]
    tc = (c.get('target_classification') or '—')[:26]
    print(f"{c['score_overall']:<6.1f} {c['name'][:40]:<42} {c['asrs_group']:<12} {tc:<28} {rel+lead:<14} {sig}")
