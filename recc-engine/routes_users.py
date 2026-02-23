import json
import os
from typing import List, Optional

import numpy as np
from fastapi import APIRouter, HTTPException, Query

import user
from api_helpers import update_keyword_counts, validate_user_id
from api_schemas import RatingRequest, Recommendation, SyncRequest, UserCreate, WatchlistRequest
from app_shared import logger, tmdb_client


router = APIRouter()


@router.post("/encode")
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

        persona_embeddings_list = []
        for p_title in user_data.personas:
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

        final_embedding = np.mean(persona_embeddings_list, axis=0).tolist()

        profile = {
            "name": user_data.name,
            "genres": user_data.genres,
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

        validate_user_id(user_data.name)
        file_path = f"users/{user_data.name}.json"
        user.save_user_profile(file_path, profile)

        query_text = user.build_user_text(profile)
        user.upsert_user_profile(user_data.name, query_text, final_embedding, profile)

        return {
            "message": f"User {user_data.name} initialized with personas: {user_data.personas}",
            "profile_preview": profile,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}")
def get_user_profile(user_id: str):
    validate_user_id(user_id)
    file_path = f"users/{user_id}.json"
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="User profile not found")

    try:
        return user.load_user_profile(file_path)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/watchlist")
def add_to_watchlist(user_id: str, request: WatchlistRequest):
    try:
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail="User profile not found")

        updated_profile = user.update_user_data(file_path, request.movie_id, "watchlist")
        return {"message": "Added to watchlist", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/users/{user_id}/watchlist/{movie_id}")
def remove_from_watchlist(user_id: str, movie_id: int):
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


@router.post("/users/{user_id}/ratings")
def rate_movie(user_id: str, request: RatingRequest):
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

        action_map = {"like": "liked", "dislike": "disliked", "neutral": "neutral"}
        updated_profile = user.update_user_data(
            file_path, request.movie_id, action_map[request.rating]
        )

        if request.rating == "like":
            try:
                kw_resp = tmdb_client.keywords(request.movie_id)
                keywords_data = kw_resp.get("keywords", [])
                new_kws = [k["name"] for k in keywords_data if "name" in k]

                current_keywords_data = updated_profile.get("keywords", {})
                updated_keywords_dict = update_keyword_counts(
                    current_keywords_data, new_kws
                )
                updated_profile["keywords"] = updated_keywords_dict

                user.save_user_profile(file_path, updated_profile)

                query_text = user.build_user_text(updated_profile)
                embedding = user.encode_user_text(query_text)
                user.upsert_user_profile(user_id, query_text, embedding, updated_profile)
            except Exception as tmdb_error:
                logger.warning(
                    "Failed to fetch keywords or re-embed for movie %s: %s",
                    request.movie_id,
                    tmdb_error,
                )

        return {"message": f"Movie rated {request.rating}", "data": updated_profile["data"]}

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/users/{user_id}/sync")
def sync_user_data(user_id: str, request: SyncRequest):
    try:
        logger.info("Syncing shown movies for user: %s", user_id)
        validate_user_id(user_id)
        file_path = f"users/{user_id}.json"
        if not os.path.exists(file_path):
            logger.info("Profile not found for sync: %s", file_path)
            raise HTTPException(status_code=404, detail="User profile not found")

        profile = user.load_user_profile(file_path)

        current_shown = set(profile["data"].get("shown", []))
        incoming_ids = set(request.shown_ids)
        current_shown.update(incoming_ids)
        profile["data"]["shown"] = list(current_shown)

        user.save_user_profile(file_path, profile)
        logger.info("Sync successful. Total shown now: %d", len(profile["data"]["shown"]))
        return {
            "message": "Sync successful",
            "shown_count": len(profile["data"]["shown"]),
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Sync error")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/users/{user_id}/recommendations", response_model=List[Recommendation])
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
    try:
        logger.info("Fetching recommendations for: %s", user_id)
        validate_user_id(user_id)
        embedding = None
        filter_genres = []
        exclude_ids = []

        file_path = f"users/{user_id}.json"
        profile = None
        user_keywords_list = []
        if os.path.exists(file_path):
            profile = user.load_user_profile(file_path)
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

            raw_keywords = profile.get("keywords", {})
            if isinstance(raw_keywords, list):
                user_keywords_list = raw_keywords[:100]
            elif isinstance(raw_keywords, dict):
                sorted_kws = sorted(
                    raw_keywords.items(), key=lambda item: item[1], reverse=True
                )
                user_keywords_list = [k for k, _ in sorted_kws[:100]]
        else:
            logger.info("Profile file not found: %s", file_path)

        try:
            db_result = user.get_profile_from_db(user_id)
            embedding = [db_result["embeddings"][0]]
        except ValueError:
            if profile:
                logger.info("Embedding not in DB. Encoding from profile...")
                query_text = user.build_user_text(profile)
                embedding = user.encode_user_text(query_text)
                user.upsert_user_profile(user_id, query_text, embedding, profile)
            else:
                raise HTTPException(status_code=404, detail="User not found")

        if genres:
            filter_genres = [g.strip() for g in genres.split(",")]

        if not embedding:
            raise HTTPException(
                status_code=500, detail="Failed to obtain user embedding."
            )

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
