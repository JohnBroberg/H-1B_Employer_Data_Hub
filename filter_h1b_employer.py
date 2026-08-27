import json
from pathlib import Path

import pandas as pd


base_dir = Path(__file__).resolve().parent
input_file = base_dir / 'h1b_hub.csv.gz'

# Change this value for each search.
search_term = 'Texas A&M'
canonical_name = 'TEXAS A&M UNIVERSITY'
column_to_search = 'Employer (Petitioner) Name'

unpivoted = pd.read_csv(input_file, low_memory=False)

if column_to_search not in unpivoted.columns:
    raise KeyError(f'Column not found: {column_to_search}')

matching_rows = unpivoted[
    unpivoted[column_to_search].astype('string').str.contains(
        search_term,
        case=False,
        na=False,
        regex=False,
    )
]

matching_employers = (
    matching_rows['Employer (Petitioner) Name']
    .drop_duplicates()
    .loc[lambda names: names.str.casefold() != canonical_name.casefold()]
    .sort_values()
    .tolist()
)

print(json.dumps({canonical_name: matching_employers}, indent=2))
