"""
Load top hot sheet companies from Supabase and pass to the research workflow.
Usage: py scripts/run_research.py
"""
import os, json, subprocess
from pathlib import Path

ROOT = Path(__file__).parent.parent

for line in (ROOT / '.env.local').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

print('Loading top hot sheet companies...')
r = sb.table('companies') \
    .select('id,name,asx_code,sector,asrs_group,score_overall,target_classification,sbti_status,sbti_date_updated') \
    .neq('relationship_status', 'current_client') \
    .neq('sbti_status', 'Targets set') \
    .neq('asrs_group', 'Unclassified') \
    .gt('score_overall', 0) \
    .order('score_overall', desc=True) \
    .limit(25) \
    .execute()

companies = r.data
print(f'Loaded {len(companies)} companies:')
for c in companies:
    print(f"  {c['score_overall']:.1f}  {c['name'][:45]:47} {c['asrs_group']:10} {c.get('target_classification','')}")

# Save to temp file for the workflow to read
args_path = ROOT / 'scripts' / 'workflows' / '_research_args.json'
args_path.write_text(json.dumps({'companies': companies}), encoding='utf-8')
print(f'\nSaved {len(companies)} companies to {args_path}')
print('Now run the workflow from Claude Code with:')
print('  Workflow({ scriptPath: "pollination-bd-tracker/scripts/workflows/research_hotsheet.js" })')
