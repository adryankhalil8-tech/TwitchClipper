from math import ceil

import numpy as np
import pandas as pd

from .models import ChatMessage, Spike


def aggregate_message_counts(
    messages: list[ChatMessage],
    window_seconds: int,
    vod_duration_seconds: int | None,
) -> np.ndarray:
    if window_seconds <= 0:
        raise ValueError("window_seconds must be greater than 0")

    max_msg_second = max((msg.timestamp_seconds for msg in messages), default=0)
    duration_seconds = max(max_msg_second, vod_duration_seconds or 0)

    bucket_count = max(1, ceil((duration_seconds + 1) / window_seconds))

    if not messages:
        return np.zeros(bucket_count, dtype=np.int32)

    indices = np.fromiter(
        (msg.timestamp_seconds // window_seconds for msg in messages),
        dtype=np.int64,
        count=len(messages),
    )
    counts = np.bincount(indices, minlength=bucket_count)
    return counts.astype(np.int32, copy=False)


def detect_spikes(counts: np.ndarray, window_seconds: int, sensitivity: float) -> tuple[list[Spike], float, float]:
    if counts.size == 0:
        return [], 0.0, 0.0

    mean = float(np.mean(counts))
    std_dev = float(np.std(counts))
    threshold = mean + (sensitivity * std_dev)

    spike_indices = np.flatnonzero(counts > threshold)
    spikes = [
        Spike(
            spike_time=int(index * window_seconds),
            window_comment_count=int(counts[index]),
            mean=mean,
            std_dev=std_dev,
        )
        for index in spike_indices
    ]

    return spikes, mean, std_dev


def activity_dataframe(counts: np.ndarray, window_seconds: int, sensitivity: float) -> pd.DataFrame:
    mean = float(np.mean(counts)) if counts.size else 0.0
    std_dev = float(np.std(counts)) if counts.size else 0.0
    threshold = mean + (sensitivity * std_dev)

    frame = pd.DataFrame(
        {
            "time_seconds": np.arange(counts.size, dtype=np.int32) * window_seconds,
            "comment_count": counts,
        }
    )
    frame["threshold"] = threshold
    return frame
