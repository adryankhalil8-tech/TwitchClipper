import sqlite3
from pathlib import Path
from typing import Iterable

from .models import VODMetadata


class MetadataStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vod_metadata (
                    vod_id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    user_login TEXT NOT NULL,
                    title TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    url TEXT NOT NULL,
                    duration_raw TEXT NOT NULL,
                    duration_seconds INTEGER NOT NULL,
                    saved_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    def save_vods(self, vods: Iterable[VODMetadata]) -> None:
        records = [
            (
                vod.vod_id,
                vod.user_id,
                vod.user_login,
                vod.title,
                vod.created_at.isoformat(),
                vod.url,
                vod.duration_raw,
                vod.duration_seconds,
            )
            for vod in vods
        ]
        if not records:
            return

        with sqlite3.connect(self.db_path) as conn:
            conn.executemany(
                """
                INSERT INTO vod_metadata (
                    vod_id, user_id, user_login, title, created_at, url, duration_raw, duration_seconds
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(vod_id) DO UPDATE SET
                    user_id = excluded.user_id,
                    user_login = excluded.user_login,
                    title = excluded.title,
                    created_at = excluded.created_at,
                    url = excluded.url,
                    duration_raw = excluded.duration_raw,
                    duration_seconds = excluded.duration_seconds
                """,
                records,
            )
