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


if __name__ == "__main__":
    unittest.main()
