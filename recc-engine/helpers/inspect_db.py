import chromadb
import json

def inspect_movies():
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_collection(name="movies")
    
    # Peek at 5 items to see their metadata structure
    results = collection.peek(limit=5)
    
    print(f"Total items in 'movies' collection: {collection.count()}")
    
    if not results["ids"]:
        print("Collection is empty.")
        return

    print("\nSample Movie Metadata:")
    for idx, meta in enumerate(results["metadatas"]):
        print(f"[{idx}] RAW METADATA: {meta}")
        payload_str = meta.get("payload", "{{}}")
        try:
            payload = json.loads(payload_str)
            title = payload.get("title", "Unknown")
            keywords = payload.get("keywords", [])
            genres = payload.get("genres", [])
            print(f"[{idx}] Title: {title}")
            print(f"    Genres: {genres}")
            print(f"    Keywords (Type: {type(keywords)}): {keywords}")
        except json.JSONDecodeError:
            print(f"[{idx}] Error decoding payload: {payload_str}")

if __name__ == "__main__":
    inspect_movies()
