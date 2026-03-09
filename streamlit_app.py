from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

from twitch_chat_tracker.chat_ingestion import load_chat_messages_from_bytes, load_chat_messages_from_file
from twitch_chat_tracker.clips import build_clip_segments, extract_clips_with_ffmpeg
from twitch_chat_tracker.config import load_config
from twitch_chat_tracker.spike_detection import activity_dataframe, aggregate_message_counts, detect_spikes
from twitch_chat_tracker.storage import MetadataStore
from twitch_chat_tracker.twitch_api import TwitchHelixClient


def _init_state() -> None:
    if "vods" not in st.session_state:
        st.session_state["vods"] = []
    if "user_id" not in st.session_state:
        st.session_state["user_id"] = ""
    if "user_login" not in st.session_state:
        st.session_state["user_login"] = ""
    if "analysis_vod_id" not in st.session_state:
        st.session_state["analysis_vod_id"] = ""
    if "analysis_message_count" not in st.session_state:
        st.session_state["analysis_message_count"] = 0
    if "analysis_mean" not in st.session_state:
        st.session_state["analysis_mean"] = 0.0
    if "analysis_std_dev" not in st.session_state:
        st.session_state["analysis_std_dev"] = 0.0
    if "analysis_activity_df" not in st.session_state:
        st.session_state["analysis_activity_df"] = pd.DataFrame()
    if "analysis_spikes_df" not in st.session_state:
        st.session_state["analysis_spikes_df"] = pd.DataFrame()
    if "analysis_segments" not in st.session_state:
        st.session_state["analysis_segments"] = []
    if "selected_clip_labels" not in st.session_state:
        st.session_state["selected_clip_labels"] = []
    if "selected_spikes_input" not in st.session_state:
        st.session_state["selected_spikes_input"] = ""


def _format_hh_mm_ss(total_seconds: int) -> str:
    total_seconds = max(int(total_seconds), 0)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _parse_timestamp_to_seconds(value: str) -> int:
    token = value.strip()
    if not token:
        raise ValueError("Empty timestamp value")

    if token.isdigit():
        return int(token)

    parts = token.split(":")
    if len(parts) != 3:
        raise ValueError(f"Invalid timestamp '{token}'. Use HH:MM:SS or seconds.")

    hours, minutes, seconds = parts
    if not (hours.isdigit() and minutes.isdigit() and seconds.isdigit()):
        raise ValueError(f"Invalid timestamp '{token}'. Use HH:MM:SS or seconds.")

    return int(hours) * 3600 + int(minutes) * 60 + int(seconds)


def _render_chart(activity_df: pd.DataFrame, spikes_df: pd.DataFrame, window_size: int) -> None:
    chart_df = activity_df.copy()
    chart_df["time_min"] = chart_df["time_seconds"] / 60.0

    line = alt.Chart(chart_df).mark_line().encode(
        x=alt.X("time_min:Q", title="Time (minutes)"),
        y=alt.Y("comment_count:Q", title=f"Comments per {window_size}s"),
    )
    threshold_line = alt.Chart(chart_df).mark_line(strokeDash=[6, 6]).encode(
        x="time_min:Q",
        y=alt.Y("threshold:Q", title="Threshold"),
    )

    if spikes_df.empty:
        st.altair_chart(line + threshold_line, use_container_width=True)
        return

    points_df = spikes_df.copy()
    points_df["time_min"] = points_df["spike_time"] / 60.0
    points = alt.Chart(points_df).mark_circle(color="red", size=70).encode(
        x="time_min:Q",
        y="window_comment_count:Q",
    )
    st.altair_chart(line + threshold_line + points, use_container_width=True)


def run_app() -> None:
    st.set_page_config(page_title="Twitch VOD Spike Detector", layout="wide")
    st.title("Twitch VOD Spike Detection + Clip Extraction")

    config = load_config()
    store = MetadataStore(Path("data/metadata.db"))
    _init_state()

    if not config.twitch_client_id or not config.twitch_client_secret:
        st.error("Set TWITCH_CLIENT_ID and TWITCH_CLIENT_SECRET environment variables before running.")
        st.stop()

    with st.sidebar:
        st.header("Detection Settings")
        sensitivity = st.number_input("Spike sensitivity (std dev multiplier)", min_value=0.1, value=2.0, step=0.1)
        window_size = st.number_input("Window size (seconds)", min_value=1, value=10, step=1)
        pre_buffer = st.number_input("Pre-spike buffer (seconds)", min_value=0, value=120, step=10)
        post_buffer = st.number_input("Post-spike buffer (seconds)", min_value=0, value=60, step=10)

    st.subheader("1) Fetch Stream + VODs")
    username = st.text_input("Twitch username", value="").strip()

    if st.button("Fetch VODs", type="primary"):
        if not username:
            st.warning("Enter a Twitch username.")
        else:
            try:
                client = TwitchHelixClient(config.twitch_client_id, config.twitch_client_secret)
                user_id, user_login = client.get_user_id(username)
                vods = client.get_latest_vods(user_id=user_id, user_login=user_login, count=20)

                st.session_state["vods"] = vods
                st.session_state["user_id"] = user_id
                st.session_state["user_login"] = user_login
                store.save_vods(vods)
                st.success(f"Fetched {len(vods)} VODs for {user_login} (user_id={user_id}).")
            except Exception as exc:
                st.error(str(exc))

    vods = st.session_state["vods"]
    if not vods:
        st.info("Fetch VODs to continue.")
        return

    vod_labels = [f"{vod.created_at.isoformat()} | {vod.vod_id} | {vod.title}" for vod in vods]
    selected_label = st.selectbox("Select VOD", vod_labels, index=0 if vod_labels else None)
    if not selected_label:
        st.info("Select a VOD to continue.")
        return

    selected_vod = vods[vod_labels.index(selected_label)]

    st.write(
        {
            "user_id": selected_vod.user_id,
            "vod_id": selected_vod.vod_id,
            "title": selected_vod.title,
            "created_at": selected_vod.created_at.isoformat(),
            "duration": selected_vod.duration_raw,
            "duration_seconds": selected_vod.duration_seconds,
            "url": selected_vod.url,
        }
    )

    st.subheader("2) Chat Source")
    uploaded_chat = st.file_uploader("Upload chat JSON (preferred)", type=["json"])
    default_chat_path = Path("data/chat") / f"{selected_vod.vod_id}.json"
    chat_file_path = st.text_input("or local chat JSON path", value=str(default_chat_path))

    if st.button("Analyze", type="primary"):
        try:
            if uploaded_chat is not None:
                messages = load_chat_messages_from_bytes(uploaded_chat.getvalue())
            else:
                path = Path(chat_file_path)
                if not path.exists():
                    raise FileNotFoundError(f"Chat file not found: {path}")
                messages = load_chat_messages_from_file(path)

            counts = aggregate_message_counts(messages, int(window_size), selected_vod.duration_seconds)
            spikes, mean, std_dev = detect_spikes(counts, int(window_size), float(sensitivity))
            activity_df = activity_dataframe(counts, int(window_size), float(sensitivity))

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
            segments = build_clip_segments(
                spikes=spikes,
                vod_duration_seconds=selected_vod.duration_seconds,
                pre_spike_buffer=int(pre_buffer),
                post_spike_buffer=int(post_buffer),
            )

            st.session_state["analysis_vod_id"] = selected_vod.vod_id
            st.session_state["analysis_message_count"] = len(messages)
            st.session_state["analysis_mean"] = mean
            st.session_state["analysis_std_dev"] = std_dev
            st.session_state["analysis_activity_df"] = activity_df
            st.session_state["analysis_spikes_df"] = spikes_df
            st.session_state["analysis_segments"] = segments

        except Exception as exc:
            st.error(str(exc))

    analysis_ready = st.session_state["analysis_vod_id"] == selected_vod.vod_id
    if not analysis_ready:
        st.caption("Run Analyze first, then generate/download clips.")
        return

    activity_df = st.session_state["analysis_activity_df"]
    spikes_df = st.session_state["analysis_spikes_df"]
    segments = st.session_state["analysis_segments"]
    mean = st.session_state["analysis_mean"]
    std_dev = st.session_state["analysis_std_dev"]
    message_count = st.session_state["analysis_message_count"]

    st.success(f"Analyzed {message_count} chat messages. Found {len(spikes_df)} spikes.")
    _render_chart(activity_df, spikes_df, int(window_size))

    st.write("Global stats", {"mean": mean, "std_dev": std_dev, "threshold": mean + float(sensitivity) * std_dev})
    st.subheader("Activity windows")
    activity_display = activity_df.copy()
    activity_display["timestamp"] = activity_display["time_seconds"].apply(_format_hh_mm_ss)
    activity_display = activity_display[["timestamp", "comment_count", "threshold"]]
    st.dataframe(activity_display, use_container_width=True)

    st.subheader("Detected spikes")
    spikes_display = spikes_df.copy()
    if not spikes_display.empty:
        spikes_display["timestamp"] = spikes_display["spike_time"].apply(_format_hh_mm_ss)
        spikes_display = spikes_display[["timestamp", "window_comment_count", "mean", "std_dev"]]
    st.dataframe(spikes_display, use_container_width=True)

    segments_table = pd.DataFrame(
        [
            {
                "spike_time": _format_hh_mm_ss(seg.spike_time),
                "clip_start": _format_hh_mm_ss(seg.clip_start),
                "clip_end": _format_hh_mm_ss(seg.clip_end),
            }
            for seg in segments
        ],
        columns=["spike_time", "clip_start", "clip_end"],
    )
    st.subheader("Clip windows")
    st.dataframe(segments_table, use_container_width=True)

    st.subheader("3) Clip Extraction")
    local_vod_path = st.text_input("Local VOD video file path (.mp4/.mkv)", value="")
    output_dir = st.text_input("Clip output directory", value="clips")
    clip_options = []
    option_to_spike = {}
    for seg in segments:
        spike_ts = _format_hh_mm_ss(seg.spike_time)
        clip_start = _format_hh_mm_ss(seg.clip_start)
        clip_end = _format_hh_mm_ss(seg.clip_end)
        label = f"{spike_ts} ({clip_start} -> {clip_end})"
        clip_options.append(label)
        option_to_spike[label] = spike_ts

    current_selected = st.session_state.get("selected_clip_labels", [])
    valid_selected = [label for label in current_selected if label in clip_options]
    if current_selected != valid_selected:
        st.session_state["selected_clip_labels"] = valid_selected

    selected_labels = st.multiselect(
        "Select clip windows",
        options=clip_options,
        key="selected_clip_labels",
        help="Selecting windows auto-populates the spike timestamp field below.",
    )

    if selected_labels:
        st.session_state["selected_spikes_input"] = ", ".join(option_to_spike[label] for label in selected_labels)

    selected_spikes_input = st.text_input(
        "Selected spikes (comma-separated HH:MM:SS or seconds)",
        key="selected_spikes_input",
    )

    if st.button("Generate selected clips", type="primary"):
        try:
            if not local_vod_path:
                st.warning("Set a local VOD path to extract clips.")
                return
            if not segments:
                st.info("No spikes found, no clips generated.")
                return

            selected_segments = segments
            if selected_spikes_input.strip():
                selected_seconds = {
                    _parse_timestamp_to_seconds(token)
                    for token in selected_spikes_input.split(",")
                    if token.strip()
                }
                selected_segments = [seg for seg in segments if seg.spike_time in selected_seconds]
                if not selected_segments:
                    st.warning("No spikes matched your selected timestamps. No clips generated.")
                    return

            extracted = extract_clips_with_ffmpeg(
                input_video_path=Path(local_vod_path),
                output_dir=Path(output_dir),
                streamer_name=selected_vod.user_login,
                vod_id=selected_vod.vod_id,
                segments=selected_segments,
            )
            st.subheader("Generated clips")
            for clip in extracted:
                clip_path = Path(clip.output_path or "")
                if clip_path.exists():
                    with clip_path.open("rb") as file_obj:
                        st.download_button(
                            label=f"Download {clip_path.name}",
                            data=file_obj.read(),
                            file_name=clip_path.name,
                            mime="video/mp4",
                        )
        except Exception as exc:
            st.error(str(exc))


if __name__ == "__main__":
    run_app()
