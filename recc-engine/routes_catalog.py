from typing import List

from fastapi import APIRouter, HTTPException

from api_schemas import BatchMovieRequest, Persona, Recommendation
from app_shared import tmdb_client


router = APIRouter()


@router.post("/movies/batch", response_model=List[Recommendation])
def get_movies_batch(request: BatchMovieRequest):
    """
    Fetches full movie details for a list of IDs.
    Used for hydrating user profiles on the client.
    """
    try:
        unique_ids = list(set(request.movie_ids))
        tmdb_results = tmdb_client.movie_details_batch(unique_ids)

        movies = []
        for data in tmdb_results:
            genres = [g["name"] for g in data.get("genres", [])]
            rec = Recommendation(
                movie_id=str(data.get("id")),
                title=data.get("title", "Unknown"),
                score=0.0,
                genres=genres,
                backdrop_path=data.get("backdrop_path"),
            )
            movies.append(rec)

        return movies
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
def read_root():
    return {"message": "Welcome to the Recc Engine API"}


@router.get("/onboarding/personas", response_model=List[Persona])
def get_onboarding_personas():
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
