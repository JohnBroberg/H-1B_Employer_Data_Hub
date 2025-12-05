import pandas as pd
from pathlib import Path

# Read all CSV files from the data folder
data_folder = Path('data')
csv_files = list(data_folder.glob('*.csv'))

# Merge all CSV files
dfs = [pd.read_csv(file) for file in csv_files]
merged_df = pd.concat(dfs, ignore_index=True)

# Save to a single CSV file
merged_df.to_csv('merged_data.csv', index=False)
print(f"Merged {len(csv_files)} files into 'merged_data.csv'")
print(merged_df.head())
print(f"Shape: {merged_df.shape}")


## comment to delete 