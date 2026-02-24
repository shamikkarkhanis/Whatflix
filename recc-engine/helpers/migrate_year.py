import chromadb
import json
import logging
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("migrate_year")

def migrate():
    client = chromadb.PersistentClient(path="chroma")
    collection = client.get_collection(name="movies")
    
    # Process in batches to be safe, though 7k fits in memory
    limit = 1000
    offset = 0
    total_updated = 0
    
    logger.info(f"Starting migration for collection '{collection.name}'...")
    
    while True:
        results = collection.get(
            limit=limit,
            offset=offset,
            include=["metadatas"]
        )
        
        ids = results["ids"]
        if not ids:
            break
            
        metadatas = results["metadatas"]
        updates_ids = []
        updates_metas = []
        
        for i, mid in enumerate(ids):
            meta = metadatas[i]
            payload_str = meta.get("payload", "{}")
            
            try:
                payload = json.loads(payload_str)
                release_date = payload.get("release_date")
                
                year = None
                if release_date:
                    try:
                        # Parse "YYYY-MM-DD"
                        dt = datetime.strptime(release_date, "%Y-%m-%d")
                        year = dt.year
                    except ValueError:
                        # Try just YYYY if format differs
                        if len(release_date) >= 4 and release_date[:4].isdigit():
                            year = int(release_date[:4])
                
                # Only update if we found a valid year and it's not already set (or we want to overwrite)
                if year is not None:
                    # Create a copy to update
                    new_meta = meta.copy()
                    new_meta["year"] = year
                    
                    updates_ids.append(mid)
                    updates_metas.append(new_meta)
                    
            except json.JSONDecodeError:
                logger.warning(f"Failed to decode payload for id {mid}")
                
        if updates_ids:
            collection.update(
                ids=updates_ids,
                metadatas=updates_metas
            )
            total_updated += len(updates_ids)
            logger.info(f"Updated batch {offset} - {offset + limit}. Total so far: {total_updated}")
        else:
             logger.info(f"No updates needed for batch {offset} - {offset + limit}")

        offset += limit

    logger.info(f"Migration complete. Total records updated: {total_updated}")

if __name__ == "__main__":
    migrate()
