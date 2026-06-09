import os
from pathlib import Path
import pandas as pd

for line in Path('C:/Users/angus.harman/Climate-Risk/pollination-bd-tracker/.env.local').read_text().splitlines():
    if '=' in line:
        k, v = line.split('=', 1); os.environ[k.strip()] = v.strip()

from supabase import create_client
sb = create_client(os.environ['NEXT_PUBLIC_SUPABASE_URL'], os.environ['SUPABASE_SECRET_KEY'])

r = sb.table('companies').select('*').ilike('name', '%fortescue%').execute()
for c in r.data:
    for k, v in c.items():
        if v is not None and v != False and v != '':
            print(f"  {k}: {v}")

print()
print("=== asx200 research data for Fortescue ===")
df = pd.read_csv('C:/Users/angus.harman/Climate-Risk/data/asx200_non_sbti.csv')
row = df[df['Company Name'].str.contains('Fortescue', case=False, na=False)]
if not row.empty:
    for k, v in row.iloc[0].items():
        if pd.notna(v) and v != '':
            print(f"  {k}: {v}")
