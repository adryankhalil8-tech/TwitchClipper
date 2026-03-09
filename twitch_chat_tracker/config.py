import os
from dataclasses import dataclass


@dataclass(frozen=True)
class AppConfig:
    twitch_client_id: str
    twitch_client_secret: str
    metadata_db_path: str = "data/metadata.db"


def load_config() -> AppConfig:
    client_id = os.getenv("TWITCH_CLIENT_ID", "").strip()
    client_secret = os.getenv("TWITCH_CLIENT_SECRET", "").strip()
    return AppConfig(
        twitch_client_id=client_id,
        twitch_client_secret=client_secret,
    )
