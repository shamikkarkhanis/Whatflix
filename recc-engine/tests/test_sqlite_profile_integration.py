import json
import os
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


RECC_ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RECC_ENGINE_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import app as recc_app  # noqa: E402
import user  # noqa: E402


class SQLiteProfileIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.client = TestClient(recc_app.app)

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = str(Path(self.temp_dir.name) / "user_profiles.sqlite3")
        self._prev_env_db = os.environ.get("USER_PROFILE_DB_PATH")
        self._prev_user_db_path = user._USER_PROFILE_DB_PATH

        os.environ["USER_PROFILE_DB_PATH"] = self.db_path
        user._USER_PROFILE_DB_PATH = self.db_path

    def tearDown(self):
        user._USER_PROFILE_DB_PATH = self._prev_user_db_path
        if self._prev_env_db is None:
            os.environ.pop("USER_PROFILE_DB_PATH", None)
        else:
            os.environ["USER_PROFILE_DB_PATH"] = self._prev_env_db
        self.temp_dir.cleanup()

    def test_migrates_legacy_json_profiles_into_sqlite(self):
        users_dir = Path(self.temp_dir.name) / "users"
        users_dir.mkdir()
        legacy_path = users_dir / "legacy_user.json"
        legacy_profile = {
            "id": "legacy_user",
            "name": "Legacy User",
            "genres": ["Drama"],
            "keywords": {"intense": 2},
            "personas": ["The Detective"],
            "data": {
                "liked": [10],
                "disliked": [],
                "neutral": [],
                "watchlist": [20],
                "history": [10],
                "shown": [10, 20],
            },
        }
        legacy_path.write_text(json.dumps([legacy_profile]), encoding="utf-8")

        result = user.migrate_legacy_json_profiles(
            users_dir=str(users_dir),
            delete_json=True,
        )

        self.assertEqual(result["migrated"], 1)
        self.assertEqual(result["skipped"], 0)
        self.assertEqual(result["deleted"], 1)
        self.assertFalse(legacy_path.exists())
        self.assertTrue(user.user_profile_exists("legacy_user"))

        loaded = user.load_user_profile("legacy_user")
        self.assertEqual(loaded["genres"], ["Drama"])
        self.assertEqual(loaded["data"]["watchlist"], [20])

    @patch("routes_users.services.user.upsert_user_profile")
    @patch("routes_users.services._get_persona_embedding")
    def test_sqlite_profile_route_lifecycle(self, mock_persona_embedding, mock_upsert):
        mock_persona_embedding.return_value = [0.1, 0.2, 0.3]
        mock_upsert.return_value = None

        create_resp = self.client.post(
            "/encode",
            json={
                "name": "alice",
                "genres": ["Drama"],
                "movie_ids": [550],
                "personas": ["The Detective"],
            },
        )
        self.assertEqual(create_resp.status_code, 200)

        with sqlite3.connect(self.db_path) as conn:
            row = conn.execute(
                "SELECT profile_json FROM user_profiles WHERE user_id = ?",
                ("alice",),
            ).fetchone()
        self.assertIsNotNone(row)
        persisted_profile = json.loads(row[0])
        self.assertEqual(persisted_profile["name"], "alice")

        watchlist_resp = self.client.post("/users/alice/watchlist", json={"movie_id": 157336})
        self.assertEqual(watchlist_resp.status_code, 200)

        rating_resp = self.client.post(
            "/users/alice/ratings",
            json={"movie_id": 550, "rating": "neutral"},
        )
        self.assertEqual(rating_resp.status_code, 200)

        sync_resp = self.client.post("/users/alice/sync", json={"shown_ids": [101, 102]})
        self.assertEqual(sync_resp.status_code, 200)
        self.assertEqual(sync_resp.json()["message"], "Sync successful")

        profile_resp = self.client.get("/users/alice")
        self.assertEqual(profile_resp.status_code, 200)
        profile = profile_resp.json()
        self.assertIn(157336, profile["data"]["watchlist"])
        self.assertIn(550, profile["data"]["neutral"])
        self.assertIn(550, profile["data"]["history"])
        self.assertTrue({101, 102}.issubset(set(profile["data"]["shown"])))

        mock_persona_embedding.assert_called_once()
        mock_upsert.assert_called_once()


if __name__ == "__main__":
    unittest.main()
