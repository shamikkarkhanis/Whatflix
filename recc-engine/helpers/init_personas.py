import logging
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

import user

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("recc-engine.init_personas")

personas = [
    {"title": "The Thrill Seeker", "description": "High stakes, explosions, and edge-of-your-seat action."},
    {"title": "The Dreamer", "description": "Sci-fi worlds, fantasy epics, and magical realism."},
    {"title": "The Detective", "description": "Mind-bending mysteries, true crime, and thrillers."},
    {"title": "The Romantic", "description": "Love stories, rom-coms, and heartwarming drama."},
    {"title": "The Indie Spirit", "description": "Art house, documentaries, and hidden gems."}
]

def init_personas():
    logger.info("Initializing personas...")
    
    for p in personas:
        title = p["title"]
        description = p["description"]
        
        # ID strategy: "persona_{title_slug}"
        # actually let's just use the title to be easy to map from frontend if we send titles
        # But spaces in IDs might be annoying. Let's use underscores.
        persona_id = f"persona_{title.replace(' ', '_')}"
        
        # Text to encode
        text = f"{title}. {description}"
        
        # Encode
        logger.info(f"Encoding '{title}'...")
        embedding = user.encode_user_text(text)
        
        # Create a profile object for consistency (though primarily we need the embedding)
        profile = {
            "name": title,
            "description": description,
            "is_persona": True,
            "data": {
                "liked": [], "disliked": [], "neutral": [], "watchlist": [], "history": [], "shown": []
            }
        }
        
        # Upsert
        logger.info(f"Upserting {persona_id}...")
        user.upsert_user_profile(persona_id, text, embedding, profile)
        
    logger.info("All personas initialized.")

if __name__ == "__main__":
    init_personas()
