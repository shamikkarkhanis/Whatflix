import argparse
import json
import os
import time
import logging

import chromadb
from sentence_transformers import SentenceTransformer

# Configure logging
logger = logging.getLogger("recc-engine.user")

# Global model instance
_embedding_model = None

def get_embedding_model():
    global _embedding_model
    if _embedding_model is None:
        logger.info("Initializing SentenceTransformer model...")
        _embedding_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _embedding_model

def build_user_text(profile):
    genres = profile.get("genres", [])
    # keys = profile.get("keywords", []) # Keywords used for reranking, not embedding
    parts = []
    if genres:
        parts.append("Genres: " + ", ".join(genres))
    # if keywords:
    #     parts.append("Keywords: " + ", ".join(keywords))
    return " | ".join(parts)


def load_user_profile(path):
    with open(path, "r") as f:
        data = json.load(f)
    
    if isinstance(data, list):
        if not data:
            raise ValueError(f"{path} is empty.")
        profile = data[0]
    elif isinstance(data, dict):
        profile = data
    else:
        raise ValueError(f"{path} must be a JSON object or a list of objects.")
    
    # Ensure data structure exists
    if "data" not in profile:
        profile["data"] = {
            "liked": [],
            "disliked": [],
            "neutral": [],
            "watchlist": [],
            "history": [],
            "shown": []
        }
    else:
        # Ensure all keys exist
        required_keys = ["liked", "disliked", "neutral", "watchlist", "history", "shown"]
        for key in required_keys:
            if key not in profile["data"]:
                profile["data"][key] = []
                
    return profile

def save_user_profile(path, profile):
    # Check if original file was a list (simple heuristic or we could store this state)
    # For now, we follow the convention of the existing files which seem to be lists.
    # We can check the file content if we want to be 100% sure, but let's assume list for now 
    # if that's the project standard, or check if the path exists and read it.
    
    # We will read the file first to preserve the structure (list vs dict)
    is_list = True
    if os.path.exists(path):
        with open(path, "r") as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    is_list = False
            except (json.JSONDecodeError, OSError):
                pass
    
    output_data = [profile] if is_list else profile
    
    with open(path, "w") as f:
        json.dump(output_data, f, indent=4)

def update_user_data(user_path, movie_id, action):
    profile = load_user_profile(user_path)
    data = profile["data"]
    
    try:
        movie_id = int(movie_id)
    except ValueError:
        pass 

    if action == "liked":
        if movie_id not in data["liked"]:
            data["liked"].append(movie_id)
        # Liked implies history (watched/interacted) and shown
        if movie_id not in data["history"]:
            data["history"].append(movie_id)
        if movie_id not in data["shown"]:
            data["shown"].append(movie_id)
        
        # Remove from conflicting states
        if movie_id in data["disliked"]:
            data["disliked"].remove(movie_id)
        if movie_id in data["neutral"]:
            data["neutral"].remove(movie_id)
            
    elif action == "disliked":
        if movie_id not in data["disliked"]:
            data["disliked"].append(movie_id)
        # Disliked implies history and shown
        if movie_id not in data["history"]:
            data["history"].append(movie_id)
        if movie_id not in data["shown"]:
            data["shown"].append(movie_id)
            
        # Remove from conflicting states
        if movie_id in data["liked"]:
            data["liked"].remove(movie_id)
        if movie_id in data["neutral"]:
            data["neutral"].remove(movie_id)

    elif action == "neutral":
        if movie_id not in data["neutral"]:
            data["neutral"].append(movie_id)
        # Neutral implies history (user rated it neutral) and shown
        if movie_id not in data["history"]:
            data["history"].append(movie_id)
        if movie_id not in data["shown"]:
            data["shown"].append(movie_id)
            
        # Remove from conflicting states
        if movie_id in data["liked"]:
            data["liked"].remove(movie_id)
        if movie_id in data["disliked"]:
            data["disliked"].remove(movie_id)
            
    elif action == "watchlist":
        if movie_id not in data["watchlist"]:
            data["watchlist"].append(movie_id)
            
    elif action == "history":
        if movie_id not in data["history"]:
            data["history"].append(movie_id)
        if movie_id not in data["shown"]:
            data["shown"].append(movie_id)
            
    elif action == "shown":
        if movie_id not in data["shown"]:
            data["shown"].append(movie_id)
            
    elif action == "remove_watchlist":
         if movie_id in data["watchlist"]:
            data["watchlist"].remove(movie_id)
            
    save_user_profile(user_path, profile)
    return profile


def get_profile_from_db(user_id):
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_or_create_collection(name="users")
    results = collection.get(
        ids=[user_id],
        include=["metadatas", "documents", "embeddings"],
    )
    if len(results.get("embeddings", [])) == 0 or results["embeddings"][0] is None:
        raise ValueError(f"User embedding not found for id={user_id}")
    return results


def encode_user_text(text):
    start_time = time.time()
    model = get_embedding_model()
    encoding = model.encode([text]).tolist()
    duration = time.time() - start_time
    logger.info("action encode_user_text | duration %.4fs", duration)
    return encoding


def upsert_user_profile(user_id, text, embedding, profile):
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_or_create_collection(name="users")
    collection.upsert(
        ids=[user_id],
        embeddings=embedding,
        metadatas=[{"payload": json.dumps(profile, ensure_ascii=True)}],
        documents=[text],
    )


def search_movies(embedding, top_k, filters=None, exclude_ids=None, language=None, user_keywords=None, min_year=None):
    start_time = time.time()
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_or_create_collection(name="movies")
    
    conditions = []
    
    # Genre filters (OR)
    if filters:
        genre_conditions = [{f"is_{genre}": True} for genre in filters]
        if len(genre_conditions) == 1:
            conditions.append(genre_conditions[0])
        else:
            conditions.append({"$or": genre_conditions})
            
    # Language filter
    if language:
        conditions.append({"language": language})
        
    # Year Filter (Native)
    if min_year:
        conditions.append({"year": {"$gte": min_year}})

    where_filter = None
    if len(conditions) == 1:
        where_filter = conditions[0]
    elif len(conditions) > 1:
        where_filter = {"$and": conditions}

    # Dynamic Fetching: Ensure we have enough candidates after exclusion.
    # We fetch: (items to exclude) + (items requested) + (safety buffer)
    exclude_count = len(exclude_ids) if exclude_ids else 0
    
    # INCREASED FETCH SIZE FOR RERANKING
    # We want a broad pool of "genre-relevant" movies to then filter by keyword overlap
    fetch_k = exclude_count + top_k + 200 
    fetch_k = min(max(fetch_k, 250), 3000)
    
    logger.info("action search_movies | where_filter: %s | fetch_k: %d", json.dumps(where_filter), fetch_k)
    
    results = collection.query(
        query_embeddings=embedding,
        n_results=fetch_k,
        include=["metadatas", "distances", "documents"],
        where=where_filter
    )

    # Candidates list
    candidates = []
    exclude_set = {str(eid) for eid in exclude_ids} if exclude_ids else set()
    user_kw_set = set(user_keywords) if user_keywords else set()
    
    ids = results["ids"][0]
    dists = results["distances"][0]
    metas = results["metadatas"][0]
    docs = results["documents"][0]
    
    for i in range(len(ids)):
        mid = ids[i]
        if mid in exclude_set:
            continue
            
        meta = metas[i]
        payload = json.loads(meta.get("payload", "{}"))
        
        # Calculate Keyword Overlap
        overlap_count = 0
        if user_kw_set:
            # Movie keywords are a list of dicts: [{'id':..., 'name': '...'}, ...]
            movie_kws_raw = payload.get("keywords", [])
            movie_kw_names = set()
            for mk in movie_kws_raw:
                if isinstance(mk, dict) and "name" in mk:
                    movie_kw_names.add(mk["name"])
                elif isinstance(mk, str):
                    movie_kw_names.add(mk)
            
            overlap_count = len(user_kw_set.intersection(movie_kw_names))
            
        candidates.append({
            "id": mid,
            "distance": dists[i],
            "metadata": meta,
            "document": docs[i],
            "overlap": overlap_count
        })

    # RERANKING LOGIC
    # Primary Sort: Overlap Count (Descending) -> Higher is better
    # Secondary Sort: Vector Distance (Ascending) -> Lower is better
    # To combine, we sort by tuple: (-overlap, distance)
    candidates.sort(key=lambda x: (-x["overlap"], x["distance"]))
    
    # Slice top_k
    final_candidates = candidates[:top_k]
    
    # Reconstruct result format
    new_results = {
        "ids": [[c["id"] for c in final_candidates]],
        "distances": [[c["distance"] for c in final_candidates]],
        "metadatas": [[c["metadata"] for c in final_candidates]],
        "documents": [[c["document"] for c in final_candidates]]
    }
            
    duration = time.time() - start_time
    logger.info("action search_movies | duration %.4fs | exclude_count %d | candidates_reranked %d", 
                duration, len(exclude_ids) if exclude_ids else 0, len(candidates))
    return new_results

def get_movies_by_ids(movie_ids):
    """
    Retrieves movies by their IDs from the Chroma DB.
    """
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_or_create_collection(name="movies")
    
    str_ids = [str(mid) for mid in movie_ids]
    results = collection.get(ids=str_ids)
    
    movies = []
    if results and results["ids"]:
        ids = results["ids"]
        metas = results["metadatas"]
        
        for i, mid in enumerate(ids):
            movies.append({
                "id": mid,
                "metadata": metas[i]
            })
            
    return movies


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-profile", default="users/user_1.json")
    parser.add_argument("--encode", action="store_true")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--genres", help="Comma-separated list of genres to filter by")
    args = parser.parse_args()


    if args.encode:
        profile = load_user_profile(args.user_profile)
        query_text = build_user_text(profile)
        embedding = encode_user_text(query_text)
        user_id = profile.get("id") or os.path.splitext(os.path.basename(args.user_profile))[0]
        upsert_user_profile(user_id, query_text, embedding, profile)
    else:
        user_id = os.path.splitext(os.path.basename(args.user_profile))[0]
        embedding = [get_profile_from_db(user_id)["embeddings"][0]]

    filters = []
    if args.genres:
        filters = [g.strip() for g in args.genres.split(",")]
    else:
        filters = load_user_profile(args.user_profile).get("genres", [])

    # pull user embedding from chroma
    user_keywords = load_user_profile(args.user_profile).get("keywords", [])

    results = search_movies(embedding, args.top_k, filters=filters, user_keywords=user_keywords)
    for idx, movie_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][idx]
        payload = json.loads(metadata.get("payload", "{}"))
        title = payload.get("title", "Unknown")
        backdrop = payload.get("backdrop_path", "No Backdrop")
        score = results["distances"][0][idx]
        # Calculate overlap for display (re-calculate or trust the sort order)
        # Since search_movies doesn't return the overlap count explicitly in the standard dict, 
        # we can just print the order which should be correct.
        print(f"{idx + 1}. {title} (id={movie_id}, distance={score:.4f}, backdrop={backdrop})")


if __name__ == "__main__":
    main()
