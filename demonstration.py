"""
Detects wordless stretches - the instructor demonstrating on their
instrument instead of talking - and marks them in the segment list as
their own pseudo-segments, so they survive into the transcript as
[[DEMONSTRATION]].
"""
DEMONSTRATION_TOKEN = "[[DEMONSTRATION]]"


def insert_demonstration_markers(segments: list, window_start: float, window_end: float, gap_seconds: float) -> list:
    """
    segments: [{"start", "end", "text"}, ...] sorted by start, all within
    [window_start, window_end) (a chunk's own local time window, or the
    whole video for an unchunked one).

    Returns a new list with {"start", "end", "text": "[[DEMONSTRATION]]",
    "is_marker": True} entries inserted wherever a gap of at least
    gap_seconds occurs - including before the first segment and after the
    last, relative to the window's own boundaries.
    """
    if not segments:
        return segments

    marked = []
    cursor = window_start

    for seg in segments:
        gap = seg["start"] - cursor
        if gap >= gap_seconds:
            marked.append({"start": cursor, "end": seg["start"], "text": DEMONSTRATION_TOKEN, "is_marker": True})
        marked.append(seg)
        cursor = max(cursor, seg["end"])

    trailing_gap = window_end - cursor
    if trailing_gap >= gap_seconds:
        marked.append({"start": cursor, "end": window_end, "text": DEMONSTRATION_TOKEN, "is_marker": True})

    return marked
