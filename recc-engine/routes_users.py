from typing import List, Optional

from fastapi import APIRouter, Query

import list_services
from api_schemas import (
    CreateCustomListRequest,
    CustomListDetail,
    CustomListMovieRequest,
    CustomListSummary,
    RatingRequest,
    Recommendation,
    RenameCustomListRequest,
    SyncRequest,
    UserCreate,
    WatchlistRequest,
)
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


@router.get("/users/{user_id}/lists", response_model=List[CustomListSummary])
def get_custom_lists(user_id: str):
    return list_services.list_custom_lists(user_id)


@router.post("/users/{user_id}/lists", response_model=CustomListDetail)
def create_custom_list(user_id: str, request: CreateCustomListRequest):
    return list_services.create_custom_list(user_id, request.name)


@router.get("/users/{user_id}/lists/{list_id}", response_model=CustomListDetail)
def get_custom_list(user_id: str, list_id: str):
    return list_services.get_custom_list(user_id, list_id)


@router.patch("/users/{user_id}/lists/{list_id}", response_model=CustomListDetail)
def rename_custom_list(user_id: str, list_id: str, request: RenameCustomListRequest):
    return list_services.rename_custom_list(user_id, list_id, request.name)


@router.delete("/users/{user_id}/lists/{list_id}")
def delete_custom_list(user_id: str, list_id: str):
    return list_services.delete_custom_list(user_id, list_id)


@router.post("/users/{user_id}/lists/{list_id}/movies")
def add_movie_to_custom_list(user_id: str, list_id: str, request: CustomListMovieRequest):
    return list_services.add_movie_to_custom_list(user_id, list_id, request.movie_id)


@router.delete("/users/{user_id}/lists/{list_id}/movies/{movie_id}")
def remove_movie_from_custom_list(user_id: str, list_id: str, movie_id: int):
    return list_services.remove_movie_from_custom_list(user_id, list_id, movie_id)


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
