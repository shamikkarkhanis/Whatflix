from typing import List, Optional

from pydantic import BaseModel


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
    user: Optional[str] = None
    email: Optional[str] = None
    fullName: Optional[dict] = None


class BatchMovieRequest(BaseModel):
    movie_ids: List[int]

class CreateCustomListRequest(BaseModel):
    name: str


class RenameCustomListRequest(BaseModel):
    name: str


class CustomListMovieRequest(BaseModel):
    movie_id: int


class CustomListSummary(BaseModel):
    list_id: str
    name: str
    movie_count: int
    created_at: str
    updated_at: str


class CustomListDetail(BaseModel):
    list_id: str
    name: str
    movie_ids: List[int]
    created_at: str
    updated_at: str


class UserCreate(BaseModel):
    name: str
    genres: List[str]
    movie_ids: List[int]
    personas: Optional[List[str]] = []


class WatchlistRequest(BaseModel):
    movie_id: int


class RatingRequest(BaseModel):
    movie_id: int
    rating: str


class SyncRequest(BaseModel):
    shown_ids: List[int]
