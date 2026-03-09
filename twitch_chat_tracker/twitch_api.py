from datetime import datetime
from typing import Any

import requests

from .models import VODMetadata, parse_twitch_duration


class TwitchHelixClient:
    TOKEN_URL = "https://id.twitch.tv/oauth2/token"
    API_BASE = "https://api.twitch.tv/helix"

    def __init__(self, client_id: str, client_secret: str, timeout_seconds: int = 20) -> None:
        if not client_id or not client_secret:
            raise ValueError("TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET are required")

        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout_seconds = timeout_seconds
        self._session = requests.Session()
        self._access_token = self._fetch_app_access_token()

    def _fetch_app_access_token(self) -> str:
        response = self._session.post(
            self.TOKEN_URL,
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        token = payload.get("access_token")
        if not token:
            raise RuntimeError("Could not fetch Twitch app access token")
        return token

    def _headers(self) -> dict[str, str]:
        return {
            "Client-ID": self.client_id,
            "Authorization": f"Bearer {self._access_token}",
        }

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = self._session.get(
            f"{self.API_BASE}/{path.lstrip('/')}",
            headers=self._headers(),
            params=params,
            timeout=self.timeout_seconds,
        )
        response.raise_for_status()
        return response.json()

    def get_user_id(self, username: str) -> tuple[str, str]:
        payload = self._get("users", {"login": username})
        users = payload.get("data", [])
        if not users:
            raise ValueError(f"Twitch user not found: {username}")

        user = users[0]
        return user["id"], user.get("login", username)

    def get_latest_vods(self, user_id: str, user_login: str, count: int = 20) -> list[VODMetadata]:
        payload = self._get("videos", {"user_id": user_id, "type": "archive", "first": count})
        vods: list[VODMetadata] = []

        for item in payload.get("data", []):
            duration_raw = item.get("duration", "")
            vods.append(
                VODMetadata(
                    vod_id=item["id"],
                    user_id=user_id,
                    user_login=user_login,
                    title=item.get("title", "Untitled"),
                    created_at=datetime.fromisoformat(item["created_at"].replace("Z", "+00:00")),
                    url=item.get("url", ""),
                    duration_raw=duration_raw,
                    duration_seconds=parse_twitch_duration(duration_raw),
                )
            )

        return vods
