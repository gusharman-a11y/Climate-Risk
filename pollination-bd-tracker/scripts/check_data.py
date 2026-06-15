import pandas as pd
from pathlib import Path

DATA = Path('C:/Users/angus.harman/Climate-Risk/data')
CER = DATA / 'cer'

# Check baselines-and-emissions
print('=== baselines-and-emissions.csv ===')
df = pd.read_csv(CER / 'baselines-and-emissions.csv')
print('Rows:', len(df), '| Cols:', list(df.columns))
print(df.head(3).to_string())

print()
print('=== nger_2024_25.xlsx ===')
df2 = pd.read_excel(DATA / 'nger_2024_25.xlsx.xlsx')
print('Rows:', len(df2), '| Cols:', list(df2.columns))
print(df2.head(5).to_string())

print()
print('=== SBTi AU companies sample ===')
sbti = pd.read_excel(DATA / 'sbti_companies.xlsx')
au = sbti[sbti['location'] == 'Australia'][['company_name','near_term_status','date_updated']].head(20)
print(au.to_string())
