# Twitch VOD Spike Detection + Clip Extraction

Functional Twitch VOD analyzer with:
- Twitch Helix API integration (user + VOD retrieval)
- Chat replay ingestion from JSON
- Time-bucketed spike detection
- Clip window generation
- ffmpeg clip extraction
- Streamlit UI

## Features

1. Stream and VOD retrieval (Helix)
- Input a Twitch username
- Resolves `user_id`
- Fetches latest VOD metadata (`vod_id`, title, duration, created_at, URL)
- Saves metadata to local SQLite: `data/metadata.db`

2. Chat ingestion
- Upload chat JSON in UI or point to a local JSON file path
- Normalizes each message to:
```json
{
  "timestamp_seconds": 123,
  "message": "...",
  "user": "..."
}
```

3. Spike detection
- Aggregates comments into time buckets (default 10 seconds)
- Computes global mean + std dev over window counts
- Spike condition:
`comments_in_window > mean + (sensitivity * std_dev)`
- Sensitivity configurable in UI (default `2.0`)

4. Clip windows
- For each spike:
  - `clip_start = spike_time - pre_buffer` (default `120s`)
  - `clip_end = spike_time + post_buffer` (default `60s`)
- Clamped to VOD bounds

5. Clip extraction
- Uses local VOD file + `ffmpeg`
- Naming format:
`{streamer}_{vod_id}_{timestamp}.mp4`

6. UI
- Username input
- VOD selector
- Configurable sensitivity/window/pre/post
- Analyze button
- Activity chart + spike markers
- Spike and clip tables
- Download buttons for generated clips

## Project Structure

```text
Twitch-Chat-Tracker/
  streamlit_app.py
  main.py
  requirements.txt
  data/
  twitch_chat_tracker/
    __init__.py
    config.py
    models.py
    twitch_api.py
    storage.py
    chat_ingestion.py
    spike_detection.py
    clips.py
```

## Setup

1. Create and activate virtual environment.
2. Install dependencies:
```bash
pip install -r requirements.txt
```
3. Set environment variables (no hardcoded secrets):

PowerShell:
```powershell
$env:TWITCH_CLIENT_ID="your_client_id"
$env:TWITCH_CLIENT_SECRET="your_client_secret"
```

4. Ensure `ffmpeg` is installed and available in PATH for clip extraction.

## Run UI

From `Twitch-Chat-Tracker`:
```bash
streamlit run streamlit_app.py
```

## Run CLI (optional)

```bash
python main.py --chat-json chat.json --vod-duration 7200 --window-size 10 --sensitivity 2.0 --pre-buffer 120 --post-buffer 60
```

With clip extraction:
```bash
python main.py --chat-json chat.json --vod-duration 7200 --extract-clips --vod-file vod.mp4 --streamer user --vod-id 12345
```

## Notes

- Twitch Helix does not provide chat replay comments directly in the same way as VOD metadata; this project consumes pre-downloaded chat JSON.
- The aggregation approach scales efficiently for long streams (for example up to 6 hours) using vectorized bucketing.
