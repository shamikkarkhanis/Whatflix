import sqlite3
import uuid
from typing import Any

from fastapi import HTTPException

import user
from api_helpers import validate_user_id
from app_shared import logger


def _connect() -> sqlite3.Connection:
    user._ensure_user_profile_db()
    conn = sqlite3.connect(user._USER_PROFILE_DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_custom_list_tables(conn)
    return conn


def _ensure_custom_list_tables(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_lists (
            list_id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            name TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_user_lists_user_id ON user_lists(user_id)"
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS user_list_items (
            list_id TEXT NOT NULL,
            movie_id INTEGER NOT NULL,
            position INTEGER NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (list_id, movie_id),
            FOREIGN KEY (list_id) REFERENCES user_lists(list_id) ON DELETE CASCADE
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_user_list_items_list_id_position
        ON user_list_items(list_id, position)
        """
    )


def _require_user_profile(user_id: str) -> str:
    validate_user_id(user_id)
    if not user.user_profile_exists(user_id):
        raise HTTPException(status_code=404, detail="User profile not found")
    return user_id


def _normalize_list_name(name: str) -> str:
    normalized = (name or "").strip()
    if not normalized:
        raise HTTPException(status_code=400, detail="List name is required")
    if len(normalized) > 64:
        raise HTTPException(status_code=400, detail="List name must be 64 characters or fewer")
    return normalized


def _summary_from_row(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "list_id": row["list_id"],
        "name": row["name"],
        "movie_count": row["movie_count"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _load_list_detail(conn: sqlite3.Connection, user_id: str, list_id: str) -> dict[str, Any]:
    row = conn.execute(
        """
        SELECT list_id, user_id, name, created_at, updated_at
        FROM user_lists
        WHERE list_id = ? AND user_id = ?
        """,
        (list_id, user_id),
    ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Custom list not found")

    item_rows = conn.execute(
        """
        SELECT movie_id
        FROM user_list_items
        WHERE list_id = ?
        ORDER BY position ASC
        """,
        (list_id,),
    ).fetchall()
    return {
        "list_id": row["list_id"],
        "name": row["name"],
        "movie_ids": [int(item["movie_id"]) for item in item_rows],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _ensure_name_unique(conn: sqlite3.Connection, user_id: str, name: str, exclude_list_id: str | None = None) -> None:
    query = """
        SELECT list_id
        FROM user_lists
        WHERE user_id = ? AND lower(name) = lower(?)
    """
    params: tuple[Any, ...] = (user_id, name)
    if exclude_list_id:
        query += " AND list_id != ?"
        params = (user_id, name, exclude_list_id)

    existing = conn.execute(query, params).fetchone()
    if existing is not None:
        raise HTTPException(status_code=409, detail="A list with that name already exists")


def list_custom_lists(user_id: str) -> list[dict[str, Any]]:
    user_id = _require_user_profile(user_id)
    try:
        with _connect() as conn:
            rows = conn.execute(
                """
                SELECT ul.list_id, ul.name, ul.created_at, ul.updated_at,
                       COUNT(uli.movie_id) AS movie_count
                FROM user_lists ul
                LEFT JOIN user_list_items uli ON uli.list_id = ul.list_id
                WHERE ul.user_id = ?
                GROUP BY ul.list_id, ul.name, ul.created_at, ul.updated_at
                ORDER BY ul.updated_at DESC, ul.created_at DESC
                """,
                (user_id,),
            ).fetchall()
            return [_summary_from_row(row) for row in rows]
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to list custom lists")
        raise HTTPException(status_code=500, detail=str(exc))


def create_custom_list(user_id: str, name: str) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    normalized_name = _normalize_list_name(name)
    list_id = f"clst_{uuid.uuid4().hex[:12]}"
    try:
        with _connect() as conn:
            _ensure_name_unique(conn, user_id, normalized_name)
            conn.execute(
                """
                INSERT INTO user_lists (list_id, user_id, name)
                VALUES (?, ?, ?)
                """,
                (list_id, user_id, normalized_name),
            )
            conn.commit()
            return _load_list_detail(conn, user_id, list_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to create custom list")
        raise HTTPException(status_code=500, detail=str(exc))


def get_custom_list(user_id: str, list_id: str) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    try:
        with _connect() as conn:
            return _load_list_detail(conn, user_id, list_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to get custom list")
        raise HTTPException(status_code=500, detail=str(exc))


def rename_custom_list(user_id: str, list_id: str, name: str) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    normalized_name = _normalize_list_name(name)
    try:
        with _connect() as conn:
            _load_list_detail(conn, user_id, list_id)
            _ensure_name_unique(conn, user_id, normalized_name, exclude_list_id=list_id)
            conn.execute(
                """
                UPDATE user_lists
                SET name = ?, updated_at = CURRENT_TIMESTAMP
                WHERE list_id = ? AND user_id = ?
                """,
                (normalized_name, list_id, user_id),
            )
            conn.commit()
            return _load_list_detail(conn, user_id, list_id)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to rename custom list")
        raise HTTPException(status_code=500, detail=str(exc))


def delete_custom_list(user_id: str, list_id: str) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    try:
        with _connect() as conn:
            _load_list_detail(conn, user_id, list_id)
            conn.execute(
                "DELETE FROM user_lists WHERE list_id = ? AND user_id = ?",
                (list_id, user_id),
            )
            conn.commit()
            return {"message": "Custom list deleted"}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to delete custom list")
        raise HTTPException(status_code=500, detail=str(exc))


def add_movie_to_custom_list(user_id: str, list_id: str, movie_id: int) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    try:
        movie_id = int(movie_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid movie ID")

    try:
        with _connect() as conn:
            _load_list_detail(conn, user_id, list_id)
            existing = conn.execute(
                "SELECT 1 FROM user_list_items WHERE list_id = ? AND movie_id = ?",
                (list_id, movie_id),
            ).fetchone()
            if existing is None:
                max_position_row = conn.execute(
                    "SELECT COALESCE(MAX(position), -1) AS max_position FROM user_list_items WHERE list_id = ?",
                    (list_id,),
                ).fetchone()
                next_pos = int(max_position_row["max_position"]) + 1
                conn.execute(
                    """
                    INSERT INTO user_list_items (list_id, movie_id, position)
                    VALUES (?, ?, ?)
                    """,
                    (list_id, movie_id, next_pos),
                )
                conn.execute(
                    "UPDATE user_lists SET updated_at = CURRENT_TIMESTAMP WHERE list_id = ?",
                    (list_id,),
                )
                message = "Movie added to list"
            else:
                message = "Movie already in list"
            conn.commit()
            return {"message": message, "list": _load_list_detail(conn, user_id, list_id)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to add movie to custom list")
        raise HTTPException(status_code=500, detail=str(exc))


def remove_movie_from_custom_list(user_id: str, list_id: str, movie_id: int) -> dict[str, Any]:
    user_id = _require_user_profile(user_id)
    try:
        movie_id = int(movie_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid movie ID")

    try:
        with _connect() as conn:
            _load_list_detail(conn, user_id, list_id)
            deleted = conn.execute(
                "DELETE FROM user_list_items WHERE list_id = ? AND movie_id = ?",
                (list_id, movie_id),
            ).rowcount
            if deleted:
                rows = conn.execute(
                    """
                    SELECT movie_id
                    FROM user_list_items
                    WHERE list_id = ?
                    ORDER BY position ASC
                    """,
                    (list_id,),
                ).fetchall()
                for idx, row in enumerate(rows):
                    conn.execute(
                        """
                        UPDATE user_list_items
                        SET position = ?
                        WHERE list_id = ? AND movie_id = ?
                        """,
                        (idx, list_id, row["movie_id"]),
                    )
                conn.execute(
                    "UPDATE user_lists SET updated_at = CURRENT_TIMESTAMP WHERE list_id = ?",
                    (list_id,),
                )
                message = "Movie removed from list"
            else:
                message = "Movie not in list"
            conn.commit()
            return {"message": message, "list": _load_list_detail(conn, user_id, list_id)}
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Failed to remove movie from custom list")
        raise HTTPException(status_code=500, detail=str(exc))
