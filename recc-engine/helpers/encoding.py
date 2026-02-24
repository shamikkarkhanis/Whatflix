import json
from datetime import datetime

import chromadb
from sentence_transformers import SentenceTransformer


def build_text(item):
    genre_names = [g.get("name") for g in item.get("genres", []) if g.get("name")]
    keyword_names = [
        k.get("name") for k in item.get("keywords", []) if k.get("name")
    ]
    overview = item.get("overview") or ""
    parts = []
    if genre_names:
        parts.append("Genres: " + ", ".join(genre_names))
    if keyword_names:
        parts.append("Keywords: " + ", ".join(keyword_names))
    if overview:
        parts.append("Overview: " + overview)
    return " | ".join(parts)


with open("data/movies.json", "r") as f:
    data = json.load(f)

client = chromadb.PersistentClient(path="chroma")
collection = client.get_or_create_collection(name="movies")

model = SentenceTransformer("all-MiniLM-L6-v2")

all_ids = []
all_documents = []
all_metadatas = []

print(f"Preparing data for {len(data)} items...")
for item in data:
    # Fallback: if no backdrop, use poster_path
    if not item.get("backdrop_path"):
        item["backdrop_path"] = item.get("poster_path")

    all_ids.append(str(item.get("id")))
    all_documents.append(build_text(item))
    
    # Add 'language' to metadata for filtering
    metadata = {
        "payload": json.dumps(item),
        "language": item.get("original_language", "unknown")
    }
    
    # Add 'year' for filtering
    release_date = item.get("release_date")
    if release_date:
        try:
            # Try YYYY-MM-DD
            dt = datetime.strptime(release_date, "%Y-%m-%d")
            metadata["year"] = dt.year
        except ValueError:
            # Fallback: Try just extracting first 4 digits
            if len(release_date) >= 4 and release_date[:4].isdigit():
                metadata["year"] = int(release_date[:4])
    
    for g in item.get("genres", []):
        name = g.get("name")
        if name:
            metadata[f"is_{name}"] = True 
            
    all_metadatas.append(metadata)

# Define batch size (Chroma limit is approx 5400, so 5000 is safe)
BATCH_SIZE = 5000
total_items = len(all_ids)

for i in range(0, total_items, BATCH_SIZE):
    batch_end = min(i + BATCH_SIZE, total_items)
    print(f"\nProcessing batch: {i} to {batch_end} (Total: {total_items})")
    
    batch_ids = all_ids[i:batch_end]
    batch_docs = all_documents[i:batch_end]
    batch_meta = all_metadatas[i:batch_end]
    
    print(f"Encoding {len(batch_docs)} documents...")
    batch_embeddings = model.encode(batch_docs, show_progress_bar=True).tolist()
    
    print(f"Upserting batch to ChromaDB...")
    collection.upsert(
        ids=batch_ids,
        embeddings=batch_embeddings,
        metadatas=batch_meta,
        documents=batch_docs,
    )

print("\nEncoding and indexing complete.")
