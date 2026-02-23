"""
TMDB API custom wrapper.
This module replaces the 'tmdbsimple' dependency with a direct requests-based client
to avoid conflicts and maintain a lightweight implementation.
"""

import logging
from typing import Optional, List, Dict, Any

import requests


logger = logging.getLogger("recc-engine.tmdb")


class TMDBClient:
    """Small convenience wrapper to keep TMDB calls in one place."""

    def __init__(self, api_key: Optional[str] = None) -> None:
        self._api_key = api_key
        self._base_url = "https://api.themoviedb.org/3/"
        self.header = {"Authorization": f"Bearer {self._api_key}"}

    def _get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        response = requests.get(
            url=self._base_url + endpoint, headers=self.header, params=params
        )
        response.raise_for_status()
        return response.json()

    def movie_details(self, movie_id: int) -> Dict[str, Any]:
        return self._get(f"movie/{movie_id}?language=en-US")

    def movie_details_batch(self, movie_ids: List[int]) -> List[Dict[str, Any]]:
        """
        Fetches details for multiple movies.
        Note: TMDB does not have a batch endpoint, so this loops.
        For production, this should be cached or rate-limited.
        """
        results = []
        for mid in movie_ids:
            try:
                data = self.movie_details(mid)
                results.append(data)
            except Exception as e:
                logger.warning("Failed to fetch details for %s: %s", mid, e)
        return results

    def keywords(self, movie_id: int) -> Dict[str, Any]:
        return self._get(f"movie/{movie_id}/keywords")

    def discover_movies(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Wrapper for /discover/movie.
        params example: {"primary_release_year": 1999, "with_genres": 27}
        """
        return self._get("discover/movie", params=params)

    def popular_movies(self, page: int = 1) -> Dict[str, Any]:
        return self._get("movie/popular", params={"page": page})
