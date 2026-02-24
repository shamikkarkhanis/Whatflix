import json

with open('tmdb_dataset.json', 'r') as f:
    data = json.load(f)

# Keep the item ONLY if None is not among its values
cleaned_data = [item for item in data if None not in item.values()]

with open('tmdb_dataset_cleaned.json', 'w') as f:
    json.dump(cleaned_data, f, indent=4)