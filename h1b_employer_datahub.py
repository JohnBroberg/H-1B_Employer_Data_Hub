"""Build a normalized, analyst-friendly H-1B employer dataset for dashboarding and portfolio storytelling.

This script ingests annual H-1B CSV files, standardizes inconsistent naming conventions,
converts raw count metrics into a single clean fact table, and exports a compressed CSV that
is ready for exploration in BI tools, notebooks, or an online portfolio dashboard.

The design emphasizes reproducibility, schema consistency, and data quality — the kinds of
engineering habits that matter in production analytics work.
"""

import json
from pathlib import Path

import pandas as pd

# -----------------------------------------------------------------------------
# 1) Establish the working directory and file locations.
# -----------------------------------------------------------------------------
# Using the script's directory keeps the pipeline portable across local machines,
# notebooks, and deployment environments without depending on a fragile working directory.
base_dir = Path(__file__).resolve().parent
data_dir = base_dir / 'data'
output_unpivoted = base_dir / 'h1b_hub.csv.gz'

csv_files = sorted(data_dir.glob('*.csv'))
print(f'Found {len(csv_files)} CSV files')

if not csv_files:
    raise FileNotFoundError(f'No CSV files found in {data_dir}')

# -----------------------------------------------------------------------------
# 2) Load each annual dataset and normalize the schema before combining them.
# -----------------------------------------------------------------------------
# This step creates a reliable longitudinal dataset by preserving the fiscal year
# from the filename and fixing column naming inconsistencies across source files.
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

# Concatenate yearly files into a single table to support trend analysis across time.
consolidated = pd.concat(frames, ignore_index=True)
consolidated = consolidated.fillna({
    'Employer (Petitioner) Name': '',
    'Petitioner State': '',
    'Petitioner City': '',
    'Petitioner Zip Code': '',
})

# -----------------------------------------------------------------------------
# 3) Standardize the raw count columns into a consistent set of analytics fields.
# -----------------------------------------------------------------------------
# The source data uses several category labels for approval/denial counts. Mapping them
# into a smaller, normalized dimension makes downstream analysis more intuitive and easier
# to present in dashboards or story-driven visualizations.
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
    """Coerce messy raw count strings into a clean integer series.

    The source CSVs include blank values, commas, and text placeholders like 'N/A'.
    This function treats those as zero so the final dataset remains statistically valid
    while staying robust to inconsistent upstream reporting.
    """
    cleaned = series.astype('string').str.strip().str.replace(',', '', regex=False)
    cleaned = cleaned.replace({'': '0', 'nan': '0', 'NaN': '0', 'N/A': '0', 'NA': '0'})
    return pd.to_numeric(cleaned, errors='coerce').fillna(0).astype('int32')


for col in list(pivot_field_map.keys()):
    if col in consolidated.columns:
        consolidated[col] = clean_numeric_column(consolidated[col])

consolidated['Fiscal Year'] = consolidated['Fiscal Year'].astype('int16')

# -----------------------------------------------------------------------------
# 4) Normalize employer names using a canonical mapping configuration.
# -----------------------------------------------------------------------------
# Many organizations appear in slightly different forms across years (e.g., legal suffixes,
# abbreviations, or formatting variations). This mapping step reduces duplicate records and
# makes employer-level analysis much more trustworthy for portfolio visualizations.
with open(base_dir / 'company_mappings.json', 'r') as f:
    company_variants = json.load(f)

# Flatten the configuration into one dictionary so each variant resolves to its canonical name.
dict_emp = {variant: canonical for canonical, variants in company_variants.items() for variant in variants}

consolidated["Employer (Petitioner) Name"] = consolidated["Employer (Petitioner) Name"].replace(dict_emp)

# Use category dtype for highly repeated text columns to reduce memory usage and improve
# the efficiency of downstream filtering, grouping, and visualization tasks.
for col in ['Employer (Petitioner) Name', 'Industry (NAICS) Code', 'Petitioner State', 'Petitioner City', 'Petitioner Zip Code']:
    if col in consolidated.columns and consolidated[col].nunique(dropna=False) <= max(1000, len(consolidated) // 10):
        consolidated[col] = consolidated[col].astype('category')

# -----------------------------------------------------------------------------
# 5) Convert the dataset from a wide table into a tidy fact table for analysis.
# -----------------------------------------------------------------------------
# A wide schema is workable for raw ingestion, but business analysis is far more efficient in
# long form where each row represents one employer-year-status metric. This is a standard
# pattern for modern dashboards and data exploration tools.

# Remove any previous artifact first to avoid file-lock or permission issues in notebook-like
# environments and ensure the export reflects the latest data build.
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

# Filter out zero-value rows to keep the output concise and focused on substantive activity.
unpivoted = unpivoted[unpivoted['Pivot Field Values'] != 0].copy()
unpivoted = unpivoted.sort_values(['Fiscal Year', 'Employer (Petitioner) Name', 'Pivot Field Names', 'Pivot Field Names Subgroup']).reset_index(drop=True)
unpivoted['Fiscal Year'] = unpivoted['Fiscal Year'].astype('int16')
unpivoted['Pivot Field Names'] = unpivoted['Pivot Field Names'].astype('category')
unpivoted['Pivot Field Names Subgroup'] = unpivoted['Pivot Field Names Subgroup'].astype('category')
unpivoted['Pivot Field Values'] = unpivoted['Pivot Field Values'].astype('int32')

# Save the final clean dataset as a compressed CSV so it remains portable while keeping file size small.
unpivoted.to_csv(output_unpivoted, index=False, compression='gzip')
print(f'Saved unpivoted CSV to {output_unpivoted}')
