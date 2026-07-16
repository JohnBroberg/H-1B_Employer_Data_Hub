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
        'Fiscal Year   ': 'Fiscal_Year',
        'Employer (Petitioner) Name': 'Employer',
        'Industry (NAICS) Code': 'NAICS',
        'Tax ID': 'Tax_ID',
        'Petitioner State': 'State',
        'Petitioner City': 'City',
        'Petitioner Zip Code': 'ZIP',
        'New Employment Approval': 'Initial Approval',
        'New Employment Denial': 'Initial Denial',
        'Continuation Approval': 'Continuing Approval',
        'Continuation Denial': 'Continuing Denial',
    }

    df = df.rename(columns=rename_map)
    df['Fiscal_Year'] = year

    keep_cols = [
        'Fiscal_Year', 'Employer', 'NAICS', 'Tax_ID', 'State', 'City', 'ZIP',
        'Initial Approval', 'Initial Denial', 'Continuing Approval', 'Continuing Denial'
    ]
    df = df[[c for c in keep_cols if c in df.columns]]
    frames.append(df)

consolidated = pd.concat(frames, ignore_index=True)
consolidated = consolidated.fillna({'Employer': '', 'State': '', 'City': '', 'ZIP': ''})

value_columns = ['Initial Approval', 'Initial Denial', 'Continuing Approval', 'Continuing Denial']
for col in value_columns:
    consolidated[col] = pd.to_numeric(consolidated[col], errors='coerce').fillna(0).astype('int32')

consolidated['Fiscal_Year'] = consolidated['Fiscal_Year'].astype('int16')

for col in ['Employer', 'NAICS', 'State', 'City', 'ZIP']:
    if col in consolidated.columns and consolidated[col].nunique(dropna=False) <= max(1000, len(consolidated) // 10):
        consolidated[col] = consolidated[col].astype('category')

# Remove any existing output file first to avoid permission issues in the notebook environment
if output_unpivoted.exists():
    output_unpivoted.unlink()

unpivoted = consolidated.melt(
    id_vars=['Fiscal_Year', 'Employer', 'NAICS', 'Tax_ID', 'State', 'City', 'ZIP'],
    value_vars=value_columns,
    var_name='Petition_Type',
    value_name='Count'
)
unpivoted = unpivoted.sort_values(['Fiscal_Year', 'Employer', 'Petition_Type']).reset_index(drop=True)
unpivoted['Fiscal_Year'] = unpivoted['Fiscal_Year'].astype('int16')
unpivoted['Petition_Type'] = unpivoted['Petition_Type'].astype('category')
unpivoted['Count'] = unpivoted['Count'].astype('int32')
unpivoted.to_csv(output_unpivoted, index=False, compression='gzip')
print(f'Saved unpivoted CSV to {output_unpivoted}')
