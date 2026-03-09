import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path


def format_timestamp(total_seconds: int) -> str:
    days, remainder = divmod(total_seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{days} days {hours:02}:{minutes:02}:{seconds:02}"


def extract_counts(chat_path: Path, bucket_seconds: int) -> list[dict[str, object]]:
    with chat_path.open("r", encoding="utf-8") as f:
        chat_data = json.load(f)

    comments = chat_data.get("comments") or []
    buckets: defaultdict[int, int] = defaultdict(int)

    for comment in comments:
        try:
            seconds = float(comment.get("content_offset_seconds", 0))
        except (TypeError, ValueError):
            continue
        bucket = int(seconds // bucket_seconds) * bucket_seconds
        buckets[bucket] += 1

    rows = []
    for bucket, count in sorted(buckets.items()):
        rows.append(
            {
                "timestamp": format_timestamp(bucket),
                "message_count": count,
            }
        )
    return rows


def write_csv(rows: list[dict[str, object]], out_path: Path) -> None:
    with out_path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp", "message_count"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract timestamp and message_count buckets from Twitch chat.json"
    )
    parser.add_argument(
        "--input",
        default="chat.json",
        help="Path to input chat JSON file (default: chat.json)",
    )
    parser.add_argument(
        "--output",
        default="chat_counts_raw.csv",
        help="Path to output CSV file (default: chat_counts_raw.csv)",
    )
    parser.add_argument(
        "--bucket-seconds",
        type=int,
        default=60,
        help="Bucket size in seconds (default: 60)",
    )
    args = parser.parse_args()

    if args.bucket_seconds <= 0:
        raise SystemExit("--bucket-seconds must be greater than 0")

    chat_path = Path(args.input)
    if not chat_path.exists():
        raise SystemExit(f"Input file not found: {chat_path}")

    rows = extract_counts(chat_path, args.bucket_seconds)
    out_path = Path(args.output)
    write_csv(rows, out_path)
    print(f"Wrote {len(rows)} rows to {out_path}")


if __name__ == "__main__":
    main()
