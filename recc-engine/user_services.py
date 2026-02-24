import json
from typing import Optional

import numpy as np
from fastapi import HTTPException

import user
from api_helpers import update_keyword_counts, validate_user_id
from api_schemas import RatingRequest, SyncRequest, UserCreate, WatchlistRequest
from app_shared import logger, tmdb_client


def _require_user_profile(user_id: str) -> str:
    validate_user_id(user_id)
    if not user.user_profile_exists(user_id):
        raise HTTPException(status_code=404, detail="User profile not found")
    return user_id


def _build_initial_profile(user_data: UserCreate) -> dict:
    return {
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


def _get_persona_embedding(persona_titles: list[str]) -> list[float]:
    persona_embeddings_list = []
    for p_title in persona_titles:
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

    return np.mean(persona_embeddings_list, axis=0).tolist()


def encode_user_profile(user_data: UserCreate) -> dict:
    if not user_data.personas:
        raise HTTPException(status_code=400, detail="Personas are required for encoding.")

    try:
        final_embedding = _get_persona_embedding(user_data.personas)
        profile = _build_initial_profile(user_data)

        validate_user_id(user_data.name)
        user.save_user_profile(user_data.name, profile)

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


def get_user_profile(user_id: str) -> dict:
    profile_ref = _require_user_profile(user_id)
    try:
        return user.load_user_profile(profile_ref)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def add_to_watchlist(user_id: str, request: WatchlistRequest) -> dict:
    try:
        profile_ref = _require_user_profile(user_id)
        updated_profile = user.update_user_data(profile_ref, request.movie_id, "watchlist")
        return {"message": "Added to watchlist", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def remove_from_watchlist(user_id: str, movie_id: int) -> dict:
    try:
        profile_ref = _require_user_profile(user_id)
        updated_profile = user.update_user_data(profile_ref, movie_id, "remove_watchlist")
        return {"message": "Removed from watchlist", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def rate_movie(user_id: str, request: RatingRequest) -> dict:
    if request.rating not in ["like", "dislike", "neutral"]:
        raise HTTPException(
            status_code=400,
            detail="Invalid rating. Must be 'like', 'dislike', or 'neutral'.",
        )

    try:
        profile_ref = _require_user_profile(user_id)
        action_map = {"like": "liked", "dislike": "disliked", "neutral": "neutral"}
        updated_profile = user.update_user_data(
            profile_ref, request.movie_id, action_map[request.rating]
        )

        if request.rating == "like":
            _refresh_profile_after_like(user_id, profile_ref, request.movie_id, updated_profile)

        return {"message": f"Movie rated {request.rating}", "data": updated_profile["data"]}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _refresh_profile_after_like(
    user_id: str, profile_ref: str, movie_id: int, updated_profile: dict
) -> None:
    try:
        kw_resp = tmdb_client.keywords(movie_id)
        keywords_data = kw_resp.get("keywords", [])
        new_kws = [k["name"] for k in keywords_data if "name" in k]

        current_keywords_data = updated_profile.get("keywords", {})
        updated_keywords_dict = update_keyword_counts(current_keywords_data, new_kws)
        updated_profile["keywords"] = updated_keywords_dict

        user.save_user_profile(profile_ref, updated_profile)

        query_text = user.build_user_text(updated_profile)
        embedding = user.encode_user_text(query_text)
        user.upsert_user_profile(user_id, query_text, embedding, updated_profile)
    except Exception as tmdb_error:
        logger.warning(
            "Failed to fetch keywords or re-embed for movie %s: %s",
            movie_id,
            tmdb_error,
        )


def sync_shown(user_id: str, request: SyncRequest) -> dict:
    try:
        logger.info("Syncing shown movies for user: %s", user_id)
        profile_ref = _require_user_profile(user_id)
        profile = user.load_user_profile(profile_ref)

        current_shown = set(profile["data"].get("shown", []))
        incoming_ids = set(request.shown_ids)
        current_shown.update(incoming_ids)
        profile["data"]["shown"] = list(current_shown)

        user.save_user_profile(profile_ref, profile)
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


def get_recommendations(
    user_id: str,
    top_k: int = 20,
    genres: Optional[str] = None,
    language: Optional[str] = None,
    min_year: Optional[int] = 1995,
) -> list[dict]:
    try:
        logger.info("Fetching recommendations for: %s", user_id)
        validate_user_id(user_id)
        embedding = None
        filter_genres = []
        exclude_ids = []

        profile = None
        user_keywords_list = []
        if user.user_profile_exists(user_id):
            profile = user.load_user_profile(user_id)
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
            logger.info("Profile not found in SQLite for user_id=%s", user_id)

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
                processed_genres = _normalize_genres(payload.get("genres", []))
                recommendations.append(
                    {
                        "movie_id": str(movie_id),
                        "title": payload.get("title", "Unknown"),
                        "score": distances[idx],
                        "genres": processed_genres,
                        "backdrop_path": payload.get("backdrop_path"),
                    }
                )

        return recommendations
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def _normalize_genres(raw_genres: list) -> list[str]:
    processed_genres = []
    for genre in raw_genres:
        if isinstance(genre, dict) and "name" in genre:
            processed_genres.append(genre["name"])
        elif isinstance(genre, str):
            processed_genres.append(genre)
    return processed_genres
