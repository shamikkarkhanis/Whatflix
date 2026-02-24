import os
import sys
import tempfile
import unittest
from pathlib import Path


RECC_ENGINE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RECC_ENGINE_DIR))

from fastapi.testclient import TestClient  # noqa: E402

import app as recc_app  # noqa: E402
import user  # noqa: E402


class CustomListsIntegrationTests(unittest.TestCase):
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

        user.save_user_profile(
            "alice",
            {
                "name": "alice",
                "genres": ["Drama"],
                "keywords": {},
                "personas": [],
                "data": {
                    "liked": [],
                    "disliked": [],
                    "neutral": [],
                    "watchlist": [],
                    "history": [],
                    "shown": [],
                },
            },
        )

    def tearDown(self):
        user._USER_PROFILE_DB_PATH = self._prev_user_db_path
        if self._prev_env_db is None:
            os.environ.pop("USER_PROFILE_DB_PATH", None)
        else:
            os.environ["USER_PROFILE_DB_PATH"] = self._prev_env_db
        self.temp_dir.cleanup()

    def test_custom_list_crud_and_items(self):
        create_resp = self.client.post("/users/alice/lists", json={"name": "Date Night"})
        self.assertEqual(create_resp.status_code, 200)
        created = create_resp.json()
        list_id = created["list_id"]
        self.assertEqual(created["movie_ids"], [])

        list_resp = self.client.get("/users/alice/lists")
        self.assertEqual(list_resp.status_code, 200)
        summaries = list_resp.json()
        self.assertEqual(len(summaries), 1)
        self.assertEqual(summaries[0]["name"], "Date Night")
        self.assertEqual(summaries[0]["movie_count"], 0)

        add1 = self.client.post(f"/users/alice/lists/{list_id}/movies", json={"movie_id": 603})
        self.assertEqual(add1.status_code, 200)
        self.assertEqual(add1.json()["list"]["movie_ids"], [603])

        add2 = self.client.post(f"/users/alice/lists/{list_id}/movies", json={"movie_id": 157336})
        self.assertEqual(add2.status_code, 200)
        self.assertEqual(add2.json()["list"]["movie_ids"], [603, 157336])

        add_dupe = self.client.post(f"/users/alice/lists/{list_id}/movies", json={"movie_id": 603})
        self.assertEqual(add_dupe.status_code, 200)
        self.assertEqual(add_dupe.json()["message"], "Movie already in list")
        self.assertEqual(add_dupe.json()["list"]["movie_ids"], [603, 157336])

        get_detail = self.client.get(f"/users/alice/lists/{list_id}")
        self.assertEqual(get_detail.status_code, 200)
        self.assertEqual(get_detail.json()["movie_ids"], [603, 157336])

        rename_resp = self.client.patch(
            f"/users/alice/lists/{list_id}",
            json={"name": "Sci-Fi Date Night"},
        )
        self.assertEqual(rename_resp.status_code, 200)
        self.assertEqual(rename_resp.json()["name"], "Sci-Fi Date Night")

        remove_resp = self.client.delete(f"/users/alice/lists/{list_id}/movies/603")
        self.assertEqual(remove_resp.status_code, 200)
        self.assertEqual(remove_resp.json()["list"]["movie_ids"], [157336])

        remove_missing = self.client.delete(f"/users/alice/lists/{list_id}/movies/999999")
        self.assertEqual(remove_missing.status_code, 200)
        self.assertEqual(remove_missing.json()["message"], "Movie not in list")
        self.assertEqual(remove_missing.json()["list"]["movie_ids"], [157336])

        delete_resp = self.client.delete(f"/users/alice/lists/{list_id}")
        self.assertEqual(delete_resp.status_code, 200)
        self.assertEqual(delete_resp.json()["message"], "Custom list deleted")

        missing_after_delete = self.client.get(f"/users/alice/lists/{list_id}")
        self.assertEqual(missing_after_delete.status_code, 404)

    def test_duplicate_names_are_rejected_case_insensitive(self):
        self.assertEqual(
            self.client.post("/users/alice/lists", json={"name": "Favorites"}).status_code,
            200,
        )
        dup_resp = self.client.post("/users/alice/lists", json={"name": "favorites"})
        self.assertEqual(dup_resp.status_code, 409)


if __name__ == "__main__":
    unittest.main()
