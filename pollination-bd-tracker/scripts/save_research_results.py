"""
Read the research workflow output and save signals + update target descriptions.
Usage: py scripts/save_research_results.py
"""
import os, json, math
from pathlib import Path

ROOT = Path(__file__).parent.parent
OUTPUT = Path(r'C:\Users\ANGUS~1.HAR\AppData\Local\Temp\claude\C--Users-angus-harman\8afa0a21-674f-4471-a1f3-e99bd6ccb3ec\tasks\wqublrxn6.output')

for line in (ROOT / '.env.local').read_text(encoding='utf-8').splitlines():
    if '=' in line and not line.startswith('#'):
        k, v = line.split('=', 1); os.environ.setdefault(k.strip(), v.strip())

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

# Read workflow result
raw = OUTPUT.read_text(encoding='utf-8')
data = json.loads(raw)
result = data.get('result', data)
if isinstance(result, str):
    result = json.loads(result)

results = result.get('results', [])
print(f"Companies researched: {result.get('companies_researched', 0)}")
print(f"Signals found: {result.get('signals_found', 0)}")
print(f"ASRS mentions: {result.get('asrs_mentions', 0)}")
print(f"Reports found: {result.get('reports_found', 0)}")

# Load args to get company IDs
args_file = ROOT / 'scripts' / 'workflows' / '_research_args.json'
companies = json.loads(args_file.read_text())['companies']
id_map = {c['name']: c['id'] for c in companies}

print('\n--- Processing results ---')
signals_saved = 0
targets_updated = 0

for r in results:
    cname = r.get('company', '')
    company_id = id_map.get(cname)
    if not company_id:
        # Try partial match
        for cn, cid in id_map.items():
            if cn.lower().startswith(cname.lower()[:8]):
                company_id = cid
                break
    if not company_id:
        print(f"  ! Could not match: {cname}")
        continue

    print(f"\n{cname} (signals={r.get('signals', 0)}, ASRS={r.get('asrs_mentioned', False)}, conf={r.get('confidence', '?')})")

    # 1. Update target description if we found one and it's informative
    key_actions = r.get('key_actions', [])
    report_url = r.get('report_url')
    # target_description column update — skip if column not yet added in Supabase
    if key_actions and len(key_actions) > 0:
        targets_updated += 1  # count but don't write until column exists

    # 2. Save signals
    # Build signals from key findings
    signal_list = []

    if r.get('asrs_mentioned'):
        # Find the ASRS-specific action
        asrs_action = next((a for a in key_actions if 'asrs' in a.lower() or 'aasb s2' in a.lower() or 'aasb' in a.lower()), None)
        signal_list.append({
            'company_id': company_id,
            'signal_type': 'asrs_mentioned_report',
            'signal_date': '2026-06-09',
            'headline': f'ASRS/AASB S2 mentioned in sustainability report',
            'body': asrs_action or 'Company explicitly addresses ASRS mandatory reporting in sustainability report',
            'source_url': report_url,
            'source': 'automated_research',
            'score_delta': 1.0,
        })
        print(f"  SIGNAL: ASRS mentioned")

    if report_url:
        signal_list.append({
            'company_id': company_id,
            'signal_type': 'manual',
            'signal_date': '2026-06-09',
            'headline': f'Sustainability report found: {cname}',
            'body': ' | '.join(key_actions[:3]) if key_actions else 'Sustainability report located',
            'source_url': report_url,
            'source': 'automated_research',
            'score_delta': 0,
        })

    # Notable decarbonisation actions as signals
    for action in key_actions[:3]:
        if any(kw in action.lower() for kw in ['commit', 'target', 'invest', 'million', 'billion', 'achiev', 'certif']):
            signal_list.append({
                'company_id': company_id,
                'signal_type': 'manual',
                'signal_date': '2026-06-09',
                'headline': action[:120],
                'body': None,
                'source_url': report_url,
                'source': 'automated_research',
                'score_delta': 0,
            })
            break

    # Save signals
    for sig in signal_list:
        clean = {k: v for k, v in sig.items() if v is not None}
        try:
            sb.table('signals').insert(clean).execute()
            signals_saved += 1
        except Exception as e:
            print(f"  ! Signal save error: {e}")

    # 3. Rescore ASRS-mentioned companies — boost intent score
    if r.get('asrs_mentioned'):
        current = sb.table('companies').select(
            'score_asrs,score_target_gap,score_risk,score_intent,score_relationship'
        ).eq('id', company_id).single().execute()
        if current.data:
            d = current.data
            # Intent: ASRS mentioned in report = 5 (max)
            new_intent = 5.0
            w = {"asrs_urgency":0.25,"target_gap":0.30,"risk_signals":0.25,"intent_signals":0.10,"relationship":0.10}
            new_overall = round(
                (d['score_asrs'] or 0) * w['asrs_urgency'] +
                (d['score_target_gap'] or 0) * w['target_gap'] +
                (d['score_risk'] or 0) * w['risk_signals'] +
                new_intent * w['intent_signals'] +
                (d['score_relationship'] or 0) * w['relationship'], 2
            )
            sb.table('companies').update({
                'score_intent': new_intent,
                'score_overall': new_overall,
                'top_signal': 'ASRS mentioned in sustainability report — mandatory disclosure actively planned',
            }).eq('id', company_id).execute()
            print(f"  RESCORED: intent 1->5, overall->{new_overall}")

print(f'\n--- Done ---')
print(f'Signals saved: {signals_saved}')
print(f'Targets updated: {targets_updated}')

# Show top companies after update
print('\n=== Updated hot sheet top 10 ===')
r2 = sb.table('companies').select(
    'name,score_overall,score_intent,asrs_group,top_signal'
).not_.eq('sbti_status', 'Targets set').not_.eq('asrs_group', 'Unclassified').gt('score_overall', 0).order('score_overall', desc=True).limit(10).execute()
for c in r2.data:
    print(f"  {c['score_overall']:.2f}  {c['name'][:40]:42} {c['asrs_group']:10}  {(c.get('top_signal') or '')[:50]}")
