import argparse
from pathlib import Path

import pandas as pd

from twitch_chat_tracker.chat_ingestion import load_chat_messages_from_file
from twitch_chat_tracker.clips import build_clip_segments, extract_clips_with_ffmpeg
from twitch_chat_tracker.spike_detection import activity_dataframe, aggregate_message_counts, detect_spikes


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Analyze Twitch VOD chat and optionally extract spike clips")
    parser.add_argument("--chat-json", default="chat.json", help="Path to chat JSON file")
    parser.add_argument("--vod-duration", type=int, default=0, help="VOD duration in seconds")
    parser.add_argument("--window-size", type=int, default=10, help="Aggregation window in seconds")
    parser.add_argument("--sensitivity", type=float, default=2.0, help="Spike threshold std-dev multiplier")
    parser.add_argument("--pre-buffer", type=int, default=120, help="Seconds before spike for clip start")
    parser.add_argument("--post-buffer", type=int, default=60, help="Seconds after spike for clip end")
    parser.add_argument("--out-counts", default="chat_counts.csv", help="Output CSV for activity counts")
    parser.add_argument("--out-spikes", default="chat_spikes.csv", help="Output CSV for spikes")
    parser.add_argument("--extract-clips", action="store_true", help="Extract clips with ffmpeg")
    parser.add_argument("--vod-file", default="", help="Local VOD video file path (required for clip extraction)")
    parser.add_argument("--output-dir", default="clips", help="Output directory for generated clips")
    parser.add_argument("--streamer", default="streamer", help="Streamer name used in clip filenames")
    parser.add_argument("--vod-id", default="vod", help="VOD id used in clip filenames")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    chat_path = Path(args.chat_json)
    if not chat_path.exists():
        raise SystemExit(f"Chat JSON not found: {chat_path}")

    messages = load_chat_messages_from_file(chat_path)
    counts = aggregate_message_counts(messages, args.window_size, args.vod_duration or None)
    spikes, mean, std_dev = detect_spikes(counts, args.window_size, args.sensitivity)

    counts_df = activity_dataframe(counts, args.window_size, args.sensitivity)
    counts_df.to_csv(args.out_counts, index=False)

    spikes_df = pd.DataFrame(
        [
            {
                "spike_time": spike.spike_time,
                "window_comment_count": spike.window_comment_count,
                "mean": spike.mean,
                "std_dev": spike.std_dev,
            }
            for spike in spikes
        ],
        columns=["spike_time", "window_comment_count", "mean", "std_dev"],
    )
    spikes_df.to_csv(args.out_spikes, index=False)

    print(f"Messages analyzed: {len(messages)}")
    print(f"Mean: {mean:.3f}, Std Dev: {std_dev:.3f}, Spikes: {len(spikes)}")
    print(f"Wrote activity CSV: {args.out_counts}")
    print(f"Wrote spikes CSV: {args.out_spikes}")

    inferred_duration = int(counts_df["time_seconds"].max()) if not counts_df.empty else 0
    vod_duration = args.vod_duration or inferred_duration
    segments = build_clip_segments(spikes, vod_duration, args.pre_buffer, args.post_buffer)

    if args.extract_clips:
        if not args.vod_file:
            raise SystemExit("--vod-file is required when --extract-clips is set")

        clip_results = extract_clips_with_ffmpeg(
            input_video_path=Path(args.vod_file),
            output_dir=Path(args.output_dir),
            streamer_name=args.streamer,
            vod_id=args.vod_id,
            segments=segments,
        )
        print(f"Generated {len(clip_results)} clips in {args.output_dir}")


if __name__ == "__main__":
    main()
