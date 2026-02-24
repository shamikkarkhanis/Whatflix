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

# Configuration
DATA_FILE = "data/movies.json"
SOURCE_FILE = "test_data.json"  # Try to load this if DATA_FILE is empty
client = TMDBClient(os.getenv("TMDB_BEARER"))

def load_existing_movies():
    movies = []
    if os.path.exists(DATA_FILE):
        print(f"Loading existing data from {DATA_FILE}...")
        with open(DATA_FILE, "r") as f:
            movies = json.load(f)
    elif os.path.exists(SOURCE_FILE):
        print(f"Loading seed data from {SOURCE_FILE}...")
        with open(SOURCE_FILE, "r") as f:
            movies = json.load(f)
    return movies

def enrich_movie(movie_basic):
    """
    Takes a basic movie object (id, title) and fetches full details + keywords.
    """
    movie_id = movie_basic.get("id")
    if movie_id is None:
        return None, 0
    
    start = time.time()
    try:
        # Fetch Details
        details = client.movie_details(movie_id)
        
        # Fetch Keywords
        kw_resp = client.keywords(movie_id)
        details["keywords"] = kw_resp.get("keywords", [])
        
        duration = time.time() - start
        return details, duration
    except Exception as e:
        print(f"Failed to enrich movie {movie_id}: {e}")
        return None, 0

def main():
    # 1. Load Existing Data
    existing_movies = load_existing_movies()
    existing_ids = {m["id"] for m in existing_movies}
    print(f"Loaded {len(existing_movies)} existing movies.")

    candidates_to_fetch = []

    # 2. Strategy A: Time Machine (1980 - 2023)
    # Fetch top 10 pages (~200 movies) for each year
    print("\n--- Strategy: Time Machine ---")
    current_year = 2027
    for year in range(1995, current_year):
        print(f"Scanning year {year}...", end="\r")
        try:
            for page in range(1, 11): # Pages 1 to 10
                res = client.discover_movies({
                    "primary_release_year": year,
                    "sort_by": "popularity.desc",
                    "page": page
                })
                candidates_to_fetch.extend(res.get("results", []))
            
        except Exception as e:
            print(f"Error fetching year {year}: {e}")
            time.sleep(1)

    # 3. Strategy B: Genre Equalizer
    # Fetch top ~60 movies for specific genres to ensure coverage
    # 27: Horror, 878: Sci-Fi, 99: Documentary, 16: Animation, 10752: War, 37: Western
    # print("\n\n--- Strategy: Genre Equalizer ---")
    # target_genres = [27, 878, 99, 16, 10752, 37, 9648] 
    # for genre_id in target_genres:
    #     print(f"Scanning genre {genre_id}...", end="\r")
    #     try:
    #         for page in range(4, 10): # ~60 movies per genre
    #             res = client.discover_movies({
    #                 "with_genres": genre_id,
    #                 "sort_by": "vote_count.desc", # Get classics
    #                 "page": page
    #             })
    #             candidates_to_fetch.extend(res.get("results", []))
    #     except Exception as e:
    #         print(f"Error fetching genre {genre_id}: {e}")

    # # 4. Strategy C: Hidden Gems
    # # High rated (>7.5), decent vote count (>300), sorted by rating
    # print("\n\n--- Strategy: Hidden Gems ---")
    # try:
    #     for page in range(6, 10): # ~100 movies
    #         res = client.discover_movies({
    #             "vote_average.gte": 7.5,
    #             "vote_count.gte": 300,
    #             "sort_by": "vote_average.desc",
    #             "page": page
    #         })
    #         candidates_to_fetch.extend(res.get("results", []))
    # except Exception as e:
    #     print(f"Error fetching hidden gems: {e}")

    # 5. Deduplicate Candidates (vs Existing and Self)
    unique_candidates = []
    seen_candidates = set()
    
    for c in candidates_to_fetch:
        mid = c.get("id")
        if mid and mid not in existing_ids and mid not in seen_candidates:
            unique_candidates.append(c)
            seen_candidates.add(mid)
            
    print(f"\n\nFound {len(candidates_to_fetch)} raw candidates.")
    print(f"After deduplication: {len(unique_candidates)} NEW movies to process.")
    
    if not unique_candidates:
        print("No new movies to fetch.")
        return

    # 6. Enrich New Candidates
    print("\n--- Enriching Candidates (Details + Keywords) ---")
    new_movies = []
    completed = 0
    total = len(unique_candidates)
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        # Submit all
        future_to_movie = {executor.submit(enrich_movie, m): m for m in unique_candidates}
        
        for future in as_completed(future_to_movie):
            result, duration = future.result()
            if result:
                new_movies.append(result)
            
            completed += 1
            if completed % 10 == 0:
                print(f"Progress: {completed}/{total} ({len(new_movies)} successful)", end="\r")

    print(f"\n\nSuccessfully enriched {len(new_movies)} movies.")

    # 7. Merge and Save
    final_dataset = existing_movies + new_movies
    
    # Ensure directory exists
    os.makedirs(os.path.dirname(DATA_FILE), exist_ok=True)
    
    print(f"Saving {len(final_dataset)} total movies to {DATA_FILE}...")
    with open(DATA_FILE, "w") as f:
        json.dump(final_dataset, f, indent=2, ensure_ascii=True)
    
    print("Done!")

if __name__ == "__main__":
    main()
