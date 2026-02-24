# db
import chromadb
import json

client = chromadb.PersistentClient(path="chroma")
collection = client.get_or_create_collection(name="movies")


results = collection.query(
    query_texts=["friendly kids movies"],
    n_results=10,
    where_document={"$contains": "Kids", "$contains": "Family"}
)

for idx, movie_id in enumerate(results["ids"][0]):
        metadata = results["metadatas"][0][idx]
        payload = json.loads(metadata.get("payload", "{}"))
        title = payload.get("title", "Unknown")
        score = results["distances"][0][idx]
        print(f"{idx + 1}. {title} (id={movie_id}, distance={score:.4f})")