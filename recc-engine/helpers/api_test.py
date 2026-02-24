import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from tmdb_api import TMDBClient

load_dotenv()

client = TMDBClient(os.getenv("TMDB_BEARER"))

movies = []
pending = []
print("Fetching popular movies list...")
for page in range(1, 401):
    popular = client.popular_movies(page=page)
    pending.extend(popular.get("results", []))

total = len(pending)
completed = 0
durations = []

def enrich_movie(movie):
    movie_id = movie.get("id")
    if movie_id is None:
        return movie, 0
    
    start = time.time()
    details = client.movie_details(movie_id)
    keywords = client.keywords(movie_id)
    details["keywords"] = keywords.get("keywords", [])
    duration = time.time() - start
    
    return details, duration


global_start = time.time()
seen_ids = set()
with ThreadPoolExecutor(max_workers=8) as executor:
    futures = {executor.submit(enrich_movie, movie): movie for movie in pending}
    for future in as_completed(futures):
        try:
            result, duration = future.result()
            if result:
                movie_id = result.get("id")
                if movie_id not in seen_ids:
                    movies.append(result)
                    seen_ids.add(movie_id)
                    durations.append(duration)
        except Exception as exc:
            movie = futures[future]
            print(f"Error fetching keywords for {movie.get('id')}: {exc}")
        
        completed += 1
        avg_so_far = sum(durations) / len(durations) if durations else 0
        print(f"[{completed}/{total}] Duration: {duration:.4f}s | Avg: {avg_so_far:.4f}s")

total_duration = time.time() - global_start
print("\n--- Enrichment Metrics ---")
print(f"Total Movies Processed: {completed}")
print(f"Total Time: {total_duration:.2f}s")
if durations:
    print(f"Average Request Duration: {sum(durations)/len(durations):.4f}s")
    print(f"Min Request Duration: {min(durations):.4f}s")
    print(f"Max Request Duration: {max(durations):.4f}s")

with open("tmdb_dataset.json", "w") as f:
    json.dump(movies, f, indent=2, ensure_ascii=True)
