import json
import os
import sys

# Ensure we can import user module
sys.path.append(os.getcwd())
try:
    import user
except ImportError:
    sys.path.append(os.path.join(os.getcwd(), 'recc-engine'))
    import user

# The list of movies to check
epitome_movies = [
    "Mad Max: Fury Road",
    "Inception",
    "The Shining",
    "The Godfather",
    "The Big Lebowski",
    "Raiders of the Lost Ark",
    "Parasite",
    "The Notebook",
    "Spider-Man: Into the Spider-Verse",
    "13th"
]

print("1. Identifying Movie IDs from dataset...")
# Load dataset
data_path = "data/merged.json"
if not os.path.exists(data_path):
    data_path = "recc-engine/data/merged.json"

try:
    with open(data_path, "r") as f:
        dataset = json.load(f)
except FileNotFoundError:
    print(f"Error: Could not find {data_path}")
    sys.exit(1)

# Find IDs
found_ids = {}
for movie in dataset:
    if movie.get("title") in epitome_movies:
        title = movie["title"]
        mid = movie["id"]
        # Prefer preserving the first ID found or specific logic if duplicates exist
        if title not in found_ids:
             found_ids[title] = mid

print("\n--- Identified IDs ---")
for title, mid in found_ids.items():
    print(f"{title}: {mid}")

# Check missing
missing_in_json = set(epitome_movies) - set(found_ids.keys())
if missing_in_json:
    print(f"\nMissing from JSON: {missing_in_json}")

print("\n2. Checking ChromaDB Availability...")
# Use user.py to check ids in bulk
try:
    ids_to_check = list(found_ids.values())
    movies_in_db = user.get_movies_by_ids(ids_to_check)
    
    db_ids = {int(m["id"]) for m in movies_in_db}
    
    print("\n--- ChromaDB Status ---")
    for title, mid in found_ids.items():
        status = "✅ Indexed" if mid in db_ids else "❌ NOT in Chroma"
        print(f"{title} (ID: {mid}) -> {status}")

except Exception as e:
    print(f"Error checking ChromaDB: {e}")
