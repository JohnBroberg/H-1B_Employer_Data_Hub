import pandas as pd
from pathlib import Path

base = Path("C:/Users/jbrob/git/H-1B_Employer_Data_Hub")
files = sorted((base / "data").glob("*.csv"))
frames = []
for path in files:
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]
    df = df.rename(columns={"Fiscal Year   ": "Fiscal Year"})
    df["Fiscal Year"] = int(path.stem.split()[-1])
    frames.append(df)

consolidated = pd.concat(frames, ignore_index=True)
consolidated = consolidated.fillna({
    'Employer (Petitioner) Name': '',
    'Petitioner State': '',
    'Petitioner City': '',
    'Petitioner Zip Code': '',
})

source_cols = [
    'New Employment Approval',
    'Continuation Approval',
    'Change with Same Employer Approval',
    'Amended Approval',
]

for col in source_cols:
    if col in consolidated.columns:
        cleaned = consolidated[col].astype('string').str.strip().str.replace(',', '', regex=False)
        cleaned = cleaned.replace({'': '0', 'nan': '0', 'NaN': '0', 'N/A': '0', 'NA': '0'})
        consolidated[col] = pd.to_numeric(cleaned, errors='coerce').fillna(0).astype('int32')

source_totals = {c: int(consolidated[c].sum()) for c in source_cols if c in consolidated.columns}

out_df = pd.read_csv(base / 'h1b_hub.csv.gz', compression='gzip', low_memory=False)
output_totals = {
    c: int(out_df.loc[out_df['Pivot Field Names Subgroup'] == c, 'Pivot Field Values'].sum())
    for c in source_cols
    if c in out_df['Pivot Field Names Subgroup'].unique()
}

print('SOURCE', source_totals)
print('OUTPUT', output_totals)
print('DIFF', {k: source_totals[k] - output_totals.get(k, 0) for k in source_totals})
assert source_totals == output_totals
