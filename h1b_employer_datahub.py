import pandas as pd
from pathlib import Path
import json

base_dir = Path(__file__).resolve().parent
data_dir = base_dir / 'data'
output_unpivoted = base_dir / 'h1b_hub.csv.gz'

csv_files = sorted(data_dir.glob('*.csv'))
print(f'Found {len(csv_files)} CSV files')

if not csv_files:
    raise FileNotFoundError(f'No CSV files found in {data_dir}')

frames = []
for path in csv_files:
    year = int(path.stem.split()[-1])
    df = pd.read_csv(path, low_memory=False)
    df.columns = [str(col).strip() for col in df.columns]

    rename_map = {
        'Fiscal Year   ': 'Fiscal Year',
    }
    df = df.rename(columns=rename_map)
    df['Fiscal Year'] = year

    frames.append(df)

consolidated = pd.concat(frames, ignore_index=True)
consolidated = consolidated.fillna({'Employer (Petitioner) Name': '', 'Petitioner State': '', 'Petitioner City': '', 'Petitioner Zip Code': ''})

pivot_field_map = {
    'New Employment Approval': 'Initial Approval',
    'New Employment Denial': 'Initial Denial',
    'Continuation Approval': 'Continuing Approval',
    'Continuation Denial': 'Continuing Denial',
    'Change with Same Employer Approval': 'Continuing Approval',
    'Change with Same Employer Denial': 'Continuing Denial',
    'New Concurrent Approval': 'Initial Approval',
    'New Concurrent Denial': 'Initial Denial',
    'Change of Employer Approval': 'Continuing Approval',
    'Change of Employer Denial': 'Continuing Denial',
    'Amended Approval': 'Continuing Approval',
    'Amended Denial': 'Continuing Denial',
}


def clean_numeric_column(series):
    cleaned = series.astype('string').str.strip().str.replace(',', '', regex=False)
    cleaned = cleaned.replace({'': '0', 'nan': '0', 'NaN': '0', 'N/A': '0', 'NA': '0'})
    return pd.to_numeric(cleaned, errors='coerce').fillna(0).astype('int32')


for col in list(pivot_field_map.keys()):
    if col in consolidated.columns:
        consolidated[col] = clean_numeric_column(consolidated[col])

consolidated['Fiscal Year'] = consolidated['Fiscal Year'].astype('int16')

# Load company mappings from JSON configuration file
with open(base_dir / 'company_mappings.json', 'r') as f:
    company_variants = json.load(f)

# Build flat dictionary mapping all variants to their canonical company name
dict_emp = {variant: canonical for canonical, variants in company_variants.items() for variant in variants}

consolidated["Employer (Petitioner) Name"] = consolidated["Employer (Petitioner) Name"].replace(dict_emp)  

for col in ['Employer (Petitioner) Name', 'Industry (NAICS) Code', 'Petitioner State', 'Petitioner City', 'Petitioner Zip Code']:
    if col in consolidated.columns and consolidated[col].nunique(dropna=False) <= max(1000, len(consolidated) // 10):
        consolidated[col] = consolidated[col].astype('category')

# Remove any existing output file first to avoid permission issues in the notebook environment
if output_unpivoted.exists():
    output_unpivoted.unlink()

value_columns = [col for col in pivot_field_map if col in consolidated.columns]
if not value_columns:
    raise ValueError('No pivot value columns found in the source CSV files.')

id_vars = [col for col in consolidated.columns if col not in value_columns]
unpivoted = consolidated.melt(
    id_vars=id_vars,
    value_vars=value_columns,
    var_name='Pivot Field Names Subgroup',
    value_name='Pivot Field Values'
)
unpivoted['Pivot Field Names'] = unpivoted['Pivot Field Names Subgroup'].map(pivot_field_map)
unpivoted = unpivoted[
    id_vars + ['Pivot Field Names', 'Pivot Field Names Subgroup', 'Pivot Field Values']
]
unpivoted = unpivoted[unpivoted['Pivot Field Values'] != 0].copy()
unpivoted = unpivoted.sort_values(['Fiscal Year', 'Employer (Petitioner) Name', 'Pivot Field Names', 'Pivot Field Names Subgroup']).reset_index(drop=True)
unpivoted['Fiscal Year'] = unpivoted['Fiscal Year'].astype('int16')
unpivoted['Pivot Field Names'] = unpivoted['Pivot Field Names'].astype('category')
unpivoted['Pivot Field Names Subgroup'] = unpivoted['Pivot Field Names Subgroup'].astype('category')
unpivoted['Pivot Field Values'] = unpivoted['Pivot Field Values'].astype('int32')
unpivoted.to_csv(output_unpivoted, index=False, compression='gzip')
print(f'Saved unpivoted CSV to {output_unpivoted}')
