from typing import List, Optional

from fastapi import APIRouter, Query

from api_schemas import RatingRequest, Recommendation, SyncRequest, UserCreate, WatchlistRequest
import user_services as services


router = APIRouter()


@router.post("/encode")
def encode_user(user_data: UserCreate):
    return services.encode_user_profile(user_data)


@router.get("/users/{user_id}")
def get_user_profile(user_id: str):
    return services.get_user_profile(user_id)


@router.post("/users/{user_id}/watchlist")
def add_to_watchlist(user_id: str, request: WatchlistRequest):
    return services.add_to_watchlist(user_id, request)


@router.delete("/users/{user_id}/watchlist/{movie_id}")
def remove_from_watchlist(user_id: str, movie_id: int):
    return services.remove_from_watchlist(user_id, movie_id)


@router.post("/users/{user_id}/ratings")
def rate_movie(user_id: str, request: RatingRequest):
    return services.rate_movie(user_id, request)


@router.post("/users/{user_id}/sync")
def sync_user_data(user_id: str, request: SyncRequest):
    return services.sync_shown(user_id, request)


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
    return services.get_recommendations(
        user_id=user_id,
        top_k=top_k,
        genres=genres,
        language=language,
        min_year=min_year,
    )
