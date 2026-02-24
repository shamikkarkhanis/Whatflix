import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv

from data.tmdb_api import TMDBClient

load_dotenv()

client = TMDBClient(os.getenv("TMDB_BEARER"))

with open('tmdb_dataset_cleaned.json', 'r') as f:
    data = json.load(f)

def fetch_keywords(item):
    movie_id = item.get("id")
    keywords = client.keywords(movie_id)
    return movie_id, keywords.get("keywords", [])


total = len(data)
completed = 0

with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(fetch_keywords, item): item for item in data}
    for future in as_completed(futures):
        item = futures[future]
        try:
            _, kw = future.result()
            item["keywords"] = kw
        except Exception as exc:
            print(f"Error fetching keywords for {item.get('id')}: {exc}")
            item["keywords"] = []
        completed += 1
        print(f"Completed {completed}/{total} (movie_id={item.get('id')})")
    print(f"movie id: {id}")

with open('tmdb_dataset_with_keywords.json', 'w') as f:
    json.dump(data, f, indent=4)
