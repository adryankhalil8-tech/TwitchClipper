import json
from pathlib import Path
from typing import Any

from .models import ChatMessage


def _extract_message_text(message_obj: Any) -> str:
    if isinstance(message_obj, str):
        return message_obj

    if isinstance(message_obj, dict):
        body = message_obj.get("body")
        if isinstance(body, str):
            return body

        fragments = message_obj.get("fragments")
        if isinstance(fragments, list):
            parts: list[str] = []
            for fragment in fragments:
                if isinstance(fragment, dict):
                    text = fragment.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            return "".join(parts)

    return ""


def _extract_username(comment: dict[str, Any]) -> str:
    commenter = comment.get("commenter")
    if isinstance(commenter, dict):
        display_name = commenter.get("display_name")
        if isinstance(display_name, str):
            return display_name

        login = commenter.get("name")
        if isinstance(login, str):
            return login

    return "unknown"


def _normalize_comments(comments: list[dict[str, Any]]) -> list[ChatMessage]:
    normalized: list[ChatMessage] = []

    for comment in comments:
        try:
            seconds = int(float(comment.get("content_offset_seconds", 0)))
        except (TypeError, ValueError):
            continue

        message = _extract_message_text(comment.get("message"))
        user = _extract_username(comment)

        normalized.append(
            ChatMessage(
                timestamp_seconds=max(0, seconds),
                message=message,
                user=user,
            )
        )

    return normalized


def load_chat_messages_from_file(path: Path) -> list[ChatMessage]:
    with path.open("r", encoding="utf-8") as f:
        payload = json.load(f)

    comments = payload.get("comments")
    if not isinstance(comments, list):
        raise ValueError("Invalid chat JSON: expected top-level 'comments' list")

    return _normalize_comments(comments)


def load_chat_messages_from_bytes(data: bytes) -> list[ChatMessage]:
    payload = json.loads(data.decode("utf-8"))
    comments = payload.get("comments")
    if not isinstance(comments, list):
        raise ValueError("Invalid chat JSON: expected top-level 'comments' list")

    return _normalize_comments(comments)
