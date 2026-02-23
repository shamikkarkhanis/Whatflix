import json
import os
import time
import logging
from typing import Optional, List
import numpy as np
from logging.handlers import RotatingFileHandler

import jwt
import requests
import portalocker
from jwt.algorithms import RSAAlgorithm

from fastapi import FastAPI, HTTPException, Query, Path, Request
from pydantic import BaseModel
from dotenv import load_dotenv

from tmdb_api import TMDBClient
import user

# Configure logging with rotating file handler
os.makedirs("logs", exist_ok=True)
log_filename = "logs/server.log"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        RotatingFileHandler(log_filename, maxBytes=5 * 1024 * 1024, backupCount=3),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("recc-engine")
logger.info("Starting server. Logging to %s", log_filename)

load_dotenv()
tmdb_client = TMDBClient(os.getenv("TMDB_BEARER"))

app = FastAPI(title="Recc Engine API")


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    duration = time.time() - start_time
    logger.info(
        "path %s | method %s | duration %.4fs | status %d",
        request.url.path,
        request.method,
        duration,
        response.status_code,
    )
    return response


class Recommendation(BaseModel):
    movie_id: str
    title: str
    score: float
    genres: List[str]
    backdrop_path: Optional[str] = None


class Persona(BaseModel):
    title: str
    description: str
    color: str
    icon: str
    image: str


class AppleAuthRequest(BaseModel):
    identityToken: str
    user: Optional[str] = None  # JSON string from Apple
    email: Optional[str] = None
    fullName: Optional[dict] = None


@app.post("/auth/apple")
def apple_auth(request: AppleAuthRequest):
    """
    Verifies Apple Identity Token and issues a session token.
    Creates a user profile if one doesn't exist.
    """
    try:
        # 1. Verify Apple Token
        apple_keys_url = "https://appleid.apple.com/auth/keys"

        # Fetch Apple's public keys
        key_response = requests.get(apple_keys_url, timeout=10)
        key_response.raise_for_status()
        key_payload = key_response.json()
        keys = key_payload.get("keys", [])

        # Get the kid from the header
        header = jwt.get_unverified_header(request.identityToken)
        kid = header.get("kid")
        alg = header.get("alg")

        # Find the matching key
        key = next((k for k in keys if k["kid"] == kid), None)
        if not key:
            raise HTTPException(status_code=401, detail="Invalid token: key not found")

        public_key = RSAAlgorithm.from_jwk(json.dumps(key))

        # Decode and verify signature
        # We don't verify 'aud' strictly here as per request context, but in production we should.
        payload = jwt.decode(
            request.identityToken,
            public_key,
            algorithms=[alg],
            options={"verify_aud": False},
        )

        user_sub = payload.get("sub")
        if not user_sub:
            raise HTTPException(status_code=401, detail="Invalid token: no sub claim")

        # 2. Get or Create User
        # Use user_sub as the unique user ID
        user_id = user_sub
        file_path = f"users/{user_id}.json"
        lock_file = f"users/{user_id}.lock"

        # Ensure 'users' directory exists
        os.makedirs("users", exist_ok=True)

        profile = None

        # Atomic creation/read
        with portalocker.Lock(lock_file, timeout=5):
            if os.path.exists(file_path):
                try:
                    profile = user.load_user_profile(file_path)
                except Exception as e:
                    logger.error(f"Failed to load profile for {user_id}: {e}")
                    # If corrupt, maybe re-create? Or fail. Let's fail safe.
                    raise HTTPException(status_code=500, detail="Profile load error")
            else:
                # Create new profile
                # Parse name if provided
                name_part = "User"
                if request.fullName:
                    given = request.fullName.get("givenName", "")
                    family = request.fullName.get("familyName", "")
                    # Combine if present
                    parts = [p for p in [given, family] if p]
                    if parts:
                        name_part = " ".join(parts)

                # Create default profile structure
                profile = {
                    "id": user_id,
                    "name": name_part,
                    "email": request.email or payload.get("email"),
                    "genres": [],
                    "data": {
                        "liked": [],
                        "disliked": [],
                        "neutral": [],
                        "watchlist": [],
                        "history": [],
                        "shown": [],
                    },
                    "keywords": {},
                    "personas": [],
                }
                user.save_user_profile(file_path, profile)
                logger.info(f"Created new user profile: {user_id}")

        # 3. Generate Session Token
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            logger.warning("JWT_SECRET_KEY is not set; using development fallback secret")
            secret_key = "dev-secret"
        # Standard claims
        session_payload = {
            "sub": user_id,
            "iat": time.time(),
            "exp": time.time() + (24 * 3600 * 7),  # 7 days expiration
        }

        session_token = jwt.encode(session_payload, secret_key, algorithm="HS256")

        return {
            "token": session_token,
            "user": profile,
            "needs_onboarding": len(profile.get("personas", [])) == 0,
        }

    except HTTPException:
        raise
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")
    except Exception as e:
        logger.error(f"Auth error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class BatchMovieRequest(BaseModel):
    movie_ids: List[int]


@app.post("/movies/batch", response_model=List[Recommendation])
def get_movies_batch(request: BatchMovieRequest):
    """
    Fetches full movie details for a list of IDs.
    Used for hydrating user profiles on the client.
    """
    try:
        # Deduplicate IDs
        unique_ids = list(set(request.movie_ids))

        # Fetch from TMDB (via wrapper)
        tmdb_results = tmdb_client.movie_details_batch(unique_ids)

        movies = []
        for data in tmdb_results:
            # Map TMDB format to Recommendation/MovieDTO format
            genres = [g["name"] for g in data.get("genres", [])]

            rec = Recommendation(
                movie_id=str(data.get("id")),
                title=data.get("title", "Unknown"),
                score=0.0,  # Not applicable for direct fetch
                genres=genres,
                backdrop_path=data.get("backdrop_path"),
            )
            movies.append(rec)

        return movies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/")
def read_root():
    return {"message": "Welcome to the Recc Engine API"}


@app.get("/onboarding/personas", response_model=List[Persona])
def get_onboarding_personas():
    """
    Returns a static list of onboarding personas.
    """
    return [
        Persona(
            title="The Thrill Seeker",
            description="High stakes, explosions, and edge-of-your-seat action.",
            color="red",
            icon="flame.fill",
            image="matrix.jpg",
        ),
        Persona(
            title="The Dreamer",
            description="Sci-fi worlds, fantasy epics, and magical realism.",
            color="purple",
            icon="sparkles",
            image="interstellar.jpg",
        ),
        Persona(
            title="The Detective",
            description="Mind-bending mysteries, true crime, and thrillers.",
            color="blue",
            icon="magnifyingglass",
            image="darkknight.jpg",
        ),
        Persona(
            title="The Romantic",
            description="Love stories, rom-coms, and heartwarming drama.",
            color="pink",
            icon="heart.fill",
            image="lalaland.jpg",
        ),
        Persona(
            title="The Indie Spirit",
            description="Art house, documentaries, and hidden gems.",
            color="orange",
            icon="camera.aperture",
            image="everything.jpg",
        ),
    ]


class UserCreate(BaseModel):
    name: str
    genres: List[str]
    movie_ids: List[int]
    personas: Optional[List[str]] = []


def update_keyword_counts(profile_keywords, new_keywords):
    """
    Updates the keyword counts in the profile.
    Handles migration if profile_keywords is a list (legacy).
    """
    # Migration: Convert list to dict if necessary
    if isinstance(profile_keywords, list):
        # Assume count 1 for existing keywords in legacy list
        counts = {k: 1 for k in profile_keywords}
    else:
        counts = profile_keywords

    for kw in new_keywords:
        counts[kw] = counts.get(kw, 0) + 1

    return counts


def validate_user_id(user_id: str):
    if not user_id or user_id != os.path.basename(user_id) or user_id in [".", ".."]:
        raise HTTPException(status_code=400, detail="Invalid user ID")


@app.post("/encode")
def encode_user(user_data: UserCreate):
    """
    Creates or updates a user profile based on the provided personas.
    Retrieves embeddings for the personas, averages them, assigns to user.
    Creates an empty profile for tracking.
    """
    try:
        if not user_data.personas:
            raise HTTPException(
                status_code=400, detail="Personas are required for encoding."
            )

        # 1. Calculate Persona Embedding
        persona_embeddings_list = []
        for p_title in user_data.personas:
            # Sanitize title to match ID format: "persona_The_Thrill_Seeker"
            p_id = f"persona_{p_title.replace(' ', '_')}"
            try:
                res = user.get_profile_from_db(p_id)
                emb = res["embeddings"][0]
                if emb is not None and len(emb) > 0:
                    persona_embeddings_list.append(emb)
                logger.info("Loaded persona embedding for %s", p_id)
            except Exception as e:
                logger.warning("Persona %s not found: %s", p_id, e)

        if not persona_embeddings_list:
            raise HTTPException(status_code=400, detail="No valid personas found.")

        # Average them
        final_embedding = np.mean(persona_embeddings_list, axis=0).tolist()

        # 2. Create Empty Profile
        profile = {
            "name": user_data.name,
            "genres": user_data.genres,  # Keep genres as preference metadata
            "data": {
                "liked": [],
                "disliked": [],
                "neutral": [],
                "watchlist": [],
                "history": [],
                "shown": [],
            },
            "keywords": {},
            "personas": user_data.personas,
        }

        # Save to disk
        validate_user_id(user_data.name)
        file_path = f"users/{user_data.name}.json"
        user.save_user_profile(file_path, profile)

        # 3. Upsert to DB
        # We need 'query_text' for the DB document, though embedding is pre-calculated.
        # We can use genres + personas names.
        query_text = user.build_user_text(profile)  # Uses genres

        user.upsert_user_profile(user_data.name, query_text, final_embedding, profile)

        return {
            "message": f"User {user_data.name} initialized with personas: {user_data.personas}",
            "profile_preview": profile,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}")
def get_user_profile(user_id: str):
    """
    Returns the full user profile (watchlist, history, ratings, etc.)
    """
    validate_user_id(user_id)
    file_path = f"users/{user_id}.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="User profile not found")

    try:
        profile = user.load_user_profile(file_path)
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class WatchlistRequest(BaseModel):
    movie_id: int


@app.post("/users/{user_id}/watchlist")
def add_to_watchlist(user_id: str, request: WatchlistRequest):
    """
    Adds a movie to the user's watchlist.
    """
    try:
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="User profile not found")

        updated_profile = user.update_user_data(
            file_path, request.movie_id, "watchlist"
        )
        return {"message": "Added to watchlist", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.delete("/users/{user_id}/watchlist/{movie_id}")
def remove_from_watchlist(user_id: str, movie_id: int):
    """
    Removes a movie from the user's watchlist.
    """
    try:
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="User profile not found")

        updated_profile = user.update_user_data(file_path, movie_id, "remove_watchlist")
        return {"message": "Removed from watchlist", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RatingRequest(BaseModel):
    movie_id: int
    rating: str  # "like", "dislike", "neutral"


@app.post("/users/{user_id}/ratings")
def rate_movie(user_id: str, request: RatingRequest):
    """
    Updates the user's rating for a movie (like/dislike/neutral).
    If 'like', it fetches keywords, updates the profile, and re-encodes the user
    to provide live recommendation updates.
    """
    if request.rating not in ["like", "dislike", "neutral"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid rating. Must be 'like', 'dislike', or 'neutral'.",
        )

    try:
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="User profile not found")

        # 1. Update the local JSON data (history, liked/disliked lists)
        action_map = {"like": "liked", "dislike": "disliked", "neutral": "neutral"}
        updated_profile = user.update_user_data(
            file_path, request.movie_id, action_map[request.rating]
        )

        # 2. If liked, we need to update keywords and re-embed for live recs
        if request.rating == "like":
            try:
                # Fetch new keywords
                kw_resp = tmdb_client.keywords(request.movie_id)
                keywords_data = kw_resp.get("keywords", [])
                new_kws = [k["name"] for k in keywords_data if "name" in k]

                # Merge with existing keywords using helper to update counts
                current_keywords_data = updated_profile.get("keywords", {})
                updated_keywords_dict = update_keyword_counts(
                    current_keywords_data, new_kws
                )
                updated_profile["keywords"] = updated_keywords_dict

                # Save the keyword update to disk
                user.save_user_profile(file_path, updated_profile)

                # Re-encode and Upsert
                query_text = user.build_user_text(updated_profile)
                embedding = user.encode_user_text(query_text)
                user.upsert_user_profile(
                    user_id, query_text, embedding, updated_profile
                )
            except Exception as tmdb_error:
                logger.warning(
                    "Failed to fetch keywords or re-embed for movie %s: %s",
                    request.movie_id,
                    tmdb_error,
                )
                # We don't fail the request, just the optimization

        return {
            "message": f"Movie rated {request.rating}",
            "data": updated_profile["data"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class SyncRequest(BaseModel):
    shown_ids: List[int]


@app.post("/users/{user_id}/sync")
def sync_user_data(user_id: str, request: SyncRequest):
    """
    Syncs the list of movies already shown to the user on the frontend.
    """
    try:
        logger.info("Syncing shown movies for user: %s", user_id)
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            logger.info("Profile not found for sync: %s", file_path)
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = user.load_user_profile(file_path)

        # Update 'shown' list
        current_shown = set(profile["data"].get("shown", []))
        incoming_ids = set(request.shown_ids)
        current_shown.update(incoming_ids)
        profile["data"]["shown"] = list(current_shown)

        user.save_user_profile(file_path, profile)
        logger.info(
            "Sync successful. Total shown now: %d", len(profile["data"]["shown"])
        )
        return {
            "message": "Sync successful",
            "shown_count": len(profile["data"]["shown"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Sync error")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/users/{user_id}/recommendations", response_model=List[Recommendation])
def get_recommendations(
    user_id: str,
    top_k: int = 20,
    genres: Optional[str] = Query(
        None, description="Comma-separated list of genres to filter by"
    ),
    language: Optional[str] = Query(
        None, description="Language code to filter by (e.g. 'en', 'es')"
    ),
    min_year: Optional[int] = Query(
        1995, description="Minimum release year to filter by"
    ),
):
    """
    Get movie recommendations for a user based on their stored embedding.
    Excludes movies the user has already seen or interacted with.
    """
    try:
        logger.info("Fetching recommendations for: %s", user_id)
        validate_user_id(user_id)
        embedding = None
        filter_genres = []
        exclude_ids = []

        # 1. Try to load user profile to get exclusion list and genres
        file_path = f"users/{user_id}.json"
        profile = None
        user_keywords_list = []
        if os.path.exists(file_path):
            profile = user.load_user_profile(file_path)
            # Exclude shown, liked, disliked, and watchlist
            data = profile.get("data", {})
            exclude_ids = list(
                set(
                    data.get("shown", [])
                    + data.get("liked", [])
                    + data.get("disliked", [])
                    + data.get("watchlist", [])
                    + data.get("history", [])
                )
            )
            logger.info("Loaded profile. Exclusion list size: %d", len(exclude_ids))
            if not genres:
                filter_genres = profile.get("genres", [])

            # Process Keywords: Filter Top 100
            raw_keywords = profile.get("keywords", {})
            if isinstance(raw_keywords, list):
                # Legacy: It's a list, use all of them (or truncate if we wanted, but logic implies frequency)
                # Since we don't have frequency, we just take them all (or top 100 arbitrary)
                user_keywords_list = raw_keywords[:100]
            elif isinstance(raw_keywords, dict):
                # Sort by count (descending)
                sorted_kws = sorted(
                    raw_keywords.items(), key=lambda item: item[1], reverse=True
                )
                # Take top 100 keys
                user_keywords_list = [k for k, v in sorted_kws[:100]]

        else:
            logger.info("Profile file not found: %s", file_path)

        # 2. Try to get embedding from DB
        try:
            db_result = user.get_profile_from_db(user_id)
            embedding = [db_result["embeddings"][0]]
        except ValueError:
            # If not in DB, encode from profile
            if profile:
                logger.info("Embedding not in DB. Encoding from profile...")
                query_text = user.build_user_text(profile)
                embedding = user.encode_user_text(query_text)
                user.upsert_user_profile(user_id, query_text, embedding, profile)
            else:
                raise HTTPException(status_code=404, detail="User not found")

        # Override genres if provided in query
        if genres:
            filter_genres = [g.strip() for g in genres.split(",")]

        if not embedding:
            raise HTTPException(
                status_code=500, detail="Failed to obtain user embedding."
            )

        # 3. Search with exclusion and language filter
        results = user.search_movies(
            embedding,
            top_k,
            filters=filter_genres,
            exclude_ids=exclude_ids,
            language=language,
            user_keywords=user_keywords_list,
            min_year=min_year,
        )

        recommendations = []
        if results and results["ids"]:
            ids = results["ids"][0]
            metadatas = results["metadatas"][0]
            distances = results["distances"][0]

            logger.info("Engine returned %d candidates after exclusion", len(ids))

            for idx, movie_id in enumerate(ids):
                meta = metadatas[idx]
                payload = json.loads(meta.get("payload", "{}"))

                # Extract genre names if they are objects
                raw_genres = payload.get("genres", [])
                processed_genres = []
                for g in raw_genres:
                    if isinstance(g, dict) and "name" in g:
                        processed_genres.append(g["name"])
                    elif isinstance(g, str):
                        processed_genres.append(g)

                rec = Recommendation(
                    movie_id=str(movie_id),
                    title=payload.get("title", "Unknown"),
                    score=distances[idx],
                    genres=processed_genres,
                    backdrop_path=payload.get("backdrop_path"),
                )
                recommendations.append(rec)

        return recommendations

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
