from dataclasses import dataclass
from datetime import datetime
from typing import Optional
import re


_DURATION_RE = re.compile(r"(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?(?:(?P<seconds>\d+)s)?")


@dataclass(frozen=True)
class VODMetadata:
    vod_id: str
    user_id: str
    user_login: str
    title: str
    created_at: datetime
    url: str
    duration_raw: str
    duration_seconds: int


@dataclass(frozen=True)
class ChatMessage:
    timestamp_seconds: int
    message: str
    user: str


@dataclass(frozen=True)
class Spike:
    spike_time: int
    window_comment_count: int
    mean: float
    std_dev: float


@dataclass(frozen=True)
class ClipSegment:
    spike_time: int
    clip_start: int
    clip_end: int
    output_path: Optional[str] = None


def parse_twitch_duration(duration_raw: str) -> int:
    """Parse Twitch duration format like '3h5m10s' to seconds."""
    match = _DURATION_RE.fullmatch(duration_raw.strip())
    if not match:
        return 0

    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds
