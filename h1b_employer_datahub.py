import pandas as pd
from pathlib import Path

base_dir = Path(__file__).resolve().parent
data_dir = base_dir / 'data'
output_unpivoted = base_dir / 'h1b_employer_datahub_unpivoted.csv.gz'

csv_files = sorted(data_dir.glob('*.csv'))
print(f'Found {len(csv_files)} CSV files')

if not csv_files:
    raise FileNotFoundError(f'No CSV files found in {data_dir}')

frames = []
for path in csv_files:
    year = int(path.stem.split()[-1])
    df = pd.read_csv(path, low_memory=False)

    rename_map = {
        'Fiscal Year   ': 'Fiscal Year',
        'Employer (Petitioner) Name': 'Sort',
        'Industry (NAICS) Code': 'Industry (NAICS) Code',
        'Tax ID': 'Tax ID',
        'Petitioner State': 'Petitioner State',
        'Petitioner City': 'Petitioner City',
        'Petitioner Zip Code': 'Petitioner Zip Code',
        'New Employment Approval': 'New Employment Approval',
        'New Employment Denial': 'New Employment Denial',
        'Continuation Approval': 'Continuing Approval',
        'Continuation Denial': 'Continuing Denial',
    }

    df = df.rename(columns=rename_map)
    df['Fiscal Year'] = year

    keep_cols = [
        'Fiscal Year', 'Sort', 'Industry (NAICS) Code', 'Tax ID', 'Petitioner State', 'Petitioner City', 'Petitioner Zip Code',
        'New Employment Approval', 'New Employment Denial', 'Continuing Approval', 'Continuing Denial'
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    frames.append(df)

consolidated = pd.concat(frames, ignore_index=True)
consolidated = consolidated.fillna({'Sort': '', 'Petitioner State': '', 'Petitioner City': '', 'Petitioner Zip Code': ''})

value_columns = ['New Employment Approval', 'New Employment Denial', 'Continuing Approval', 'Continuing Denial']
for col in value_columns:
    consolidated[col] = pd.to_numeric(consolidated[col], errors='coerce').fillna(0).astype('int32')

consolidated['Fiscal Year'] = consolidated['Fiscal Year'].astype('int16')

for col in ['Sort', 'Industry (NAICS) Code', 'Petitioner State', 'Petitioner City', 'Petitioner Zip Code']:
    if col in consolidated.columns and consolidated[col].nunique(dropna=False) <= max(1000, len(consolidated) // 10):
        consolidated[col] = consolidated[col].astype('category')

# Remove any existing output file first to avoid permission issues in the notebook environment
if output_unpivoted.exists():
    output_unpivoted.unlink()

unpivoted = consolidated.melt(
    id_vars=['Fiscal Year', 'Sort', 'Tax ID', 'Industry (NAICS) Code', 'Petitioner City', 'Petitioner State', 'Petitioner Zip Code'],
    value_vars=value_columns,
    var_name='Decision',
    value_name='Petitions'
)
unpivoted = unpivoted.sort_values(['Fiscal Year', 'Sort', 'Decision']).reset_index(drop=True)
unpivoted['Fiscal Year'] = unpivoted['Fiscal Year'].astype('int16')
unpivoted['Decision'] = unpivoted['Decision'].astype('category')
unpivoted['Petitions'] = unpivoted['Petitions'].astype('int32')
unpivoted.to_csv(output_unpivoted, index=False, compression='gzip')
print(f'Saved unpivoted CSV to {output_unpivoted}')
