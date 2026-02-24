import json
import os
import sys
from pathlib import Path

import chromadb

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from user import build_user_text, encode_user_text, load_user_profile


profile = load_user_profile(os.getenv("SEARCH_USER_ID", "user_1"))
query_text = build_user_text(profile)
query_embedding = encode_user_text(query_text)

client = chromadb.PersistentClient(path="chroma")
collection = client.get_or_create_collection(name="movies")

results = collection.query(
    query_embeddings=query_embedding,
    n_results=10,
    include=["metadatas", "distances", "documents"],
)

for idx, movie_id in enumerate(results["ids"][0]):
    metadata = results["metadatas"][0][idx]
    payload = json.loads(metadata.get("payload", "{}"))
    title = payload.get("title", "Unknown")
    score = results["distances"][0][idx]
    print(f"{idx + 1}. {title} (id={movie_id}, distance={score:.4f})")
