import chromadb
import os

def check_db_count():
    try:
        client = chromadb.PersistentClient(path="chroma")
        collection = client.get_collection(name="movies")
        count = collection.count()
        print(f"Total movies in ChromaDB: {count}")
        
        # Optional: Print a few IDs to verify format
        if count > 0:
            peek = collection.peek(limit=5)
            print("Sample IDs:", peek['ids'])
            
    except Exception as e:
        print(f"Error accessing ChromaDB: {e}")

if __name__ == "__main__":
    check_db_count()
