"""
Feed it a YouTube video link and it:
  1. Checks for an existing Turkish transcript on YouTube (skips Whisper if found)
  2. Otherwise downloads the audio and transcribes it via the OpenAI Whisper API,
     splitting into multiple parts (via ffmpeg) if the audio is too big for one request
  3. Marks long wordless stretches (e.g. instrument demonstrations) as [[DEMONSTRATION]]
  4. Translates to English + generates vocab/grammar notes with GPT
  5. Writes a side-by-side HTML report per part, with the original video embedded

Run with:  python3 main.py <youtube-url> [--click-to-seek]
"""
import argparse
import json
import logging
import sys
from datetime import datetime, timezone

from config import CLICK_TO_SEEK_DEFAULT, DEMONSTRATION_GAP_SECONDS, OUTPUT_FOLDER, SERVE_PORT, TOKEN_USAGE_LOG
from demonstration import insert_demonstration_markers
from html_report import build_html_report, update_manifest, write_shared_assets
from serve import serve_and_open
from transcriber import transcribe
from translator import translate_freeform, translate_segments_aligned
from youtube_source import (
    cleanup,
    download_audio,
    extract_video_id,
    fetch_existing_transcript,
    get_video_metadata,
    needs_chunking,
    split_audio_by_time,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("youtube-transcriber")


def record_token_usage(label: str, usage: dict) -> None:
    records = []
    if TOKEN_USAGE_LOG.exists():
        try:
            records = json.loads(TOKEN_USAGE_LOG.read_text())
        except json.JSONDecodeError:
            log.warning(f"{TOKEN_USAGE_LOG} was unreadable, starting fresh.")

    records.append({
        "label": label,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        **usage,
    })

    TOKEN_USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_USAGE_LOG.write_text(json.dumps(records, indent=2))


def _gather_segment_groups(video_id: str, duration_seconds: float):
    """
    Returns a list of (segments, window_start, window_end, part, total_parts,
    source_label, apply_demonstration_markers) tuples - one entry unless the
    audio had to be chunked for Whisper, in which case one entry per
    chunk/part.

    apply_demonstration_markers is False for an existing manual transcript:
    if the transcript itself already contains YouTube-caption-convention
    tags like [Müzik] for non-speech passages, those already do the job
    [[DEMONSTRATION]] gap-detection exists for, so we don't double-mark.
    """
    existing = fetch_existing_transcript(video_id)
    if existing:
        log.info("Found an existing manually-created Turkish transcript on YouTube - skipping Whisper.")
        return [(existing, 0.0, duration_seconds, None, None, "existing YouTube captions", False)]

    log.info("No manual Turkish transcript found on YouTube - downloading audio for Whisper transcription.")
    audio_path = download_audio(video_id, OUTPUT_FOLDER / ".tmp_audio")
    try:
        if not needs_chunking(audio_path):
            log.info("Transcribing with the OpenAI Whisper API...")
            segments = transcribe(audio_path)
            return [(segments, 0.0, duration_seconds, None, None, "Whisper transcription", True)]

        chunks = split_audio_by_time(audio_path, duration_seconds)
        total_parts = len(chunks)
        groups = []
        for i, (chunk_path, start, end) in enumerate(chunks, 1):
            log.info(f"Transcribing part {i}/{total_parts} with the OpenAI Whisper API...")
            try:
                segs = transcribe(chunk_path)
            finally:
                cleanup(chunk_path)
            groups.append((segs, start, end, i, total_parts, "Whisper transcription", True))
        return groups
    finally:
        cleanup(audio_path)


def process_video(url: str, click_to_seek: bool) -> list:
    video_id = extract_video_id(url)
    meta = get_video_metadata(video_id)
    log.info(f"'{meta.title}' ({meta.duration_seconds / 60:.1f} min, id={video_id})")

    groups = _gather_segment_groups(video_id, meta.duration_seconds)

    write_shared_assets(OUTPUT_FOLDER)

    out_paths = []
    for segments, window_start, window_end, part, total_parts, source_label, apply_markers in groups:
        label = f"part {part}/{total_parts}" if part else "video"
        if apply_markers:
            marked = insert_demonstration_markers(segments, window_start, window_end, DEMONSTRATION_GAP_SECONDS)
        else:
            marked = segments

        mode = "click-to-seek" if click_to_seek else "freeform"
        log.info(f"Translating {label} with GPT ({mode} mode)...")
        result = translate_segments_aligned(marked) if click_to_seek else translate_freeform(marked)

        usage = result.pop("usage", None)
        if usage:
            record_token_usage(f"{meta.title} ({label}, {mode})", usage)

        out_path = build_html_report(
            video_title=meta.title,
            video_id=video_id,
            embed_start=window_start,
            embed_end=window_end,
            part=part,
            total_parts=total_parts,
            transcript_source=source_label,
            click_to_seek=click_to_seek,
            result=result,
            output_folder=OUTPUT_FOLDER,
            token_usage=usage,
        )
        log.info(f"Done -> {out_path}")
        out_paths.append(out_path)

    update_manifest(OUTPUT_FOLDER)
    return out_paths


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Transcribe a YouTube video's Turkish audio into a side-by-side Turkish/English HTML report."
    )
    parser.add_argument("url", help="YouTube video URL (or a bare 11-character video ID)")
    seek_group = parser.add_mutually_exclusive_group()
    seek_group.add_argument(
        "--click-to-seek", dest="click_to_seek", action="store_true", default=None,
        help="Segment-aligned translation with timestamps, so clicking a phrase seeks the embedded "
             "video there. Choppier prose than the default - see README. Writes to a "
             "'-clicktoseek' filename so it doesn't overwrite a freeform run of the same video.",
    )
    seek_group.add_argument(
        "--no-click-to-seek", dest="click_to_seek", action="store_false",
        help="Force freeform mode for this run, even if CLICK_TO_SEEK=true is set in .env.",
    )
    parser.add_argument(
        "--no-serve", dest="serve", action="store_false", default=True,
        help="Don't start a local server / open a browser when done - just write the report and "
             "exit. Useful for scripting multiple videos back to back.",
    )
    args = parser.parse_args()
    click_to_seek = CLICK_TO_SEEK_DEFAULT if args.click_to_seek is None else args.click_to_seek

    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    try:
        out_paths = process_video(args.url, click_to_seek)
    except Exception:
        log.exception(f"Failed to process {args.url}")
        sys.exit(1)

    if args.serve and out_paths:
        serve_and_open(OUTPUT_FOLDER, out_paths[0], SERVE_PORT)


if __name__ == "__main__":
    main()
