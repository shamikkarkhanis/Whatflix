import sys
import unittest
from pathlib import Path
from unittest.mock import patch


RECC_ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RECC_ENGINE_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import app as recc_app  # noqa: E402


class AppRoutesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(recc_app.app)

    def test_root_route(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"message": "Welcome to the Recc Engine API"})

    def test_personas_route(self):
        response = self.client.get("/onboarding/personas")

        self.assertEqual(response.status_code, 200)
        personas = response.json()
        self.assertGreaterEqual(len(personas), 1)
        self.assertIn("title", personas[0])
        self.assertIn("image", personas[0])

    @patch("routes_users.services.get_user_profile")
    def test_user_profile_route_delegates_to_service(self, mock_get_user_profile):
        mock_get_user_profile.return_value = {
            "name": "Alice",
            "genres": ["Drama"],
            "data": {
                "liked": [],
                "disliked": [],
                "neutral": [],
                "watchlist": [],
                "history": [],
                "shown": [],
            },
            "personas": [],
        }

        response = self.client.get("/users/alice")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Alice")
        mock_get_user_profile.assert_called_once_with("alice")

    @patch("routes_users.services.get_recommendations")
    def test_recommendations_route_passes_query_params(self, mock_get_recommendations):
        mock_get_recommendations.return_value = [
            {
                "movie_id": "1",
                "title": "Test Movie",
                "score": 0.1,
                "genres": ["Drama"],
                "backdrop_path": "/x.jpg",
            }
        ]

        response = self.client.get(
            "/users/alice/recommendations",
            params={"top_k": 5, "genres": "Drama,Comedy", "language": "en", "min_year": 2000},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()), 1)
        mock_get_recommendations.assert_called_once_with(
            user_id="alice",
            top_k=5,
            genres="Drama,Comedy",
            language="en",
            min_year=2000,
        )

    @patch("routes_users.list_services.list_custom_lists")
    def test_custom_lists_route_delegates_to_service(self, mock_list_custom_lists):
        mock_list_custom_lists.return_value = []

        response = self.client.get("/users/alice/lists")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), [])
        mock_list_custom_lists.assert_called_once_with("alice")

    @patch("routes_users.list_services.create_custom_list")
    def test_create_custom_list_route_delegates_to_service(self, mock_create_custom_list):
        mock_create_custom_list.return_value = {
            "list_id": "clst_123",
            "name": "Favorites",
            "movie_ids": [],
            "created_at": "2026-01-01 00:00:00",
            "updated_at": "2026-01-01 00:00:00",
        }

        response = self.client.post("/users/alice/lists", json={"name": "Favorites"})

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["name"], "Favorites")
        mock_create_custom_list.assert_called_once_with("alice", "Favorites")

    @patch("routes_users.list_services.add_movie_to_custom_list")
    def test_add_movie_to_custom_list_route_delegates_to_service(self, mock_add_movie):
        mock_add_movie.return_value = {
            "message": "Movie added to list",
            "list": {
                "list_id": "clst_123",
                "name": "Favorites",
                "movie_ids": [157336],
                "created_at": "2026-01-01 00:00:00",
                "updated_at": "2026-01-01 00:01:00",
            },
        }

        response = self.client.post(
            "/users/alice/lists/clst_123/movies",
            json={"movie_id": 157336},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["list"]["movie_ids"], [157336])
        mock_add_movie.assert_called_once_with("alice", "clst_123", 157336)


if __name__ == "__main__":
    unittest.main()
