import re
import shutil
import subprocess
from pathlib import Path

from .models import ClipSegment, Spike


def sanitize_filename(text: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9_-]+", "_", text.strip().lower())
    return cleaned.strip("_") or "clip"


def build_clip_segments(
    spikes: list[Spike],
    vod_duration_seconds: int,
    pre_spike_buffer: int,
    post_spike_buffer: int,
) -> list[ClipSegment]:
    segments: list[ClipSegment] = []

    for spike in spikes:
        clip_start = max(0, spike.spike_time - pre_spike_buffer)
        clip_end = min(vod_duration_seconds, spike.spike_time + post_spike_buffer)

        if clip_end <= clip_start:
            continue

        segments.append(
            ClipSegment(
                spike_time=spike.spike_time,
                clip_start=clip_start,
                clip_end=clip_end,
            )
        )

    return segments


def extract_clips_with_ffmpeg(
    input_video_path: Path,
    output_dir: Path,
    streamer_name: str,
    vod_id: str,
    segments: list[ClipSegment],
) -> list[ClipSegment]:
    ffmpeg_bin = shutil.which("ffmpeg")
    if not ffmpeg_bin:
        raise RuntimeError("ffmpeg is not installed or not in PATH")

    if not input_video_path.exists():
        raise FileNotFoundError(f"Input VOD file not found: {input_video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)

    prefix = f"{sanitize_filename(streamer_name)}_{sanitize_filename(vod_id)}"
    results: list[ClipSegment] = []

    for segment in segments:
        duration = segment.clip_end - segment.clip_start
        out_path = output_dir / f"{prefix}_{segment.spike_time}.mp4"

        cmd = [
            ffmpeg_bin,
            "-y",
            "-ss",
            str(segment.clip_start),
            "-i",
            str(input_video_path),
            "-t",
            str(duration),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-crf",
            "23",
            "-c:a",
            "aac",
            str(out_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True, text=True)
        results.append(
            ClipSegment(
                spike_time=segment.spike_time,
                clip_start=segment.clip_start,
                clip_end=segment.clip_end,
                output_path=str(out_path),
            )
        )

    return results
