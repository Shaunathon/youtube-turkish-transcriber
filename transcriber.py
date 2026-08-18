"""
Transcription via OpenAI's hosted Whisper API, with per-segment timestamps
(needed for [[DEMONSTRATION]] gap detection and click-to-seek).
"""
import logging

from openai import OpenAI

from config import OPENAI_API_KEY, SOURCE_LANGUAGE, WHISPER_TRANSCRIBE_MODEL

log = logging.getLogger("youtube-transcriber")
client = OpenAI(api_key=OPENAI_API_KEY)


def transcribe(path) -> list:
    """
    Transcribes an audio file and returns [{"start": float, "end": float,
    "text": str}, ...] in source-language text, using Whisper's segment
    timestamps.
    """
    with open(path, "rb") as f:
        transcription = client.audio.transcriptions.create(
            model=WHISPER_TRANSCRIBE_MODEL,
            file=f,
            language=SOURCE_LANGUAGE,
            response_format="verbose_json",
        )

    segments = [
        {"start": float(s.start), "end": float(s.end), "text": s.text.strip()}
        for s in (transcription.segments or [])
        if s.text.strip()
    ]
    if not segments:
        raise ValueError(f"Whisper returned no speech segments for {path} - the clip may be silent.")
    return segments
