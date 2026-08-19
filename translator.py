"""
Sends the Turkish transcript to OpenAI's chat completions API and gets back
Turkish/English sentence pairs plus vocabulary and grammar notes.

Two modes, chosen by main.py based on the --click-to-seek flag:

- translate_freeform: GPT freely resplits the whole transcript into
  natural, flowing sentences. Reads best, but the resulting pairs carry no
  timestamps.
- translate_segments_aligned: GPT groups the timestamped Whisper/caption
  segments into complete, natural sentences (never spanning a
  [[DEMONSTRATION]] marker) and translates each group as a whole - so
  prose quality matches freeform, while every pair still carries the
  timestamp of the segment it starts at (from the first segment in its
  group), driving click-to-seek. The Turkish side of each pair is
  reconstructed directly from the source segments rather than trusted to
  GPT, so it's always exactly faithful - no drift-checking needed.

Both preserve [[DEMONSTRATION]] markers as their own standalone pair.
"""
import json
import logging

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from demonstration import DEMONSTRATION_TOKEN

log = logging.getLogger("youtube-transcriber")
client = OpenAI(api_key=OPENAI_API_KEY)

_VOCAB_GRAMMAR_GUIDELINES = """
Guidelines:
- vocabulary: 5-12 words/phrases genuinely worth learning for an intermediate learner. Skip \
trivial ones (ve, bir, bu) unless the usage is notable (idiom, unusual case, etc).
- grammar_notes: 2-6 structures actually present in this transcript (suffixes, tenses, cases, \
particles, word order). Quote the relevant word or phrase from the transcript itself rather \
than giving a generic textbook explanation.
- If the transcript is very short, it is fine to return fewer vocabulary/grammar/sentence items.
"""

FREEFORM_SYSTEM_PROMPT = """You are a Turkish-English translator and language tutor helping an \
intermediate learner. You will be given a Turkish transcript from an instructional video (e.g. \
a music lesson), so it may be casual, contain false starts, or minor transcription errors - \
work around those sensibly. It may also contain the literal token [[DEMONSTRATION]] marking a \
wordless passage. Respond with ONLY valid JSON (no markdown fences, no commentary) matching \
exactly this shape:

{
  "sentence_pairs": [
    {"turkish": "one Turkish sentence, reproduced from the transcript, OR the literal token [[DEMONSTRATION]]", "english": "the matching English sentence, OR [[DEMONSTRATION]] unchanged"}
  ],
  "vocabulary": [
    {"turkish": "word or phrase as it appears", "english": "meaning", "note": "brief usage note, optional, can be empty string"}
  ],
  "grammar_notes": [
    {"topic": "short topic name, e.g. 'Passive voice (-il/-in)'", "explanation": "1-3 sentences, grounded in the actual word/phrase from this transcript"}
  ]
}

Critical rule for sentence_pairs: split the Turkish transcript into sentences FIRST, \
reproducing each Turkish sentence exactly as given (fix only obvious transcription typos, \
never rephrase or reorder words). Then give ONE matching English sentence per Turkish \
sentence - even if that English reads a little less smoothly than a freely-written paragraph \
would, each pair must correspond 1:1. Never merge two Turkish sentences into one English \
sentence, and never split one Turkish sentence into two English sentences. If a Turkish \
"sentence" is really a fragment (common in casual speech), keep it as its own pair rather \
than merging it into a neighbor. The [[DEMONSTRATION]] token, if present, must appear as its \
own pair (turkish and english both exactly "[[DEMONSTRATION]]"), never merged into a \
neighboring sentence. Concatenating all "turkish" fields in order, with single spaces between \
them, must reproduce the original transcript.

The literal token [[DEMONSTRATION]] is not Turkish - never translate it, explain it, or treat \
it as vocabulary/grammar. Leave it exactly as-is wherever it must appear in your output.
""" + _VOCAB_GRAMMAR_GUIDELINES

ALIGNED_SYSTEM_PROMPT = """You are a Turkish-English translator and language tutor helping an \
intermediate learner. You will be given a Turkish transcript from an instructional video (e.g. \
a music lesson), already split into numbered items with fixed index boundaries. Each item is \
either:
- {"index": N, "turkish": "..."} - a real segment of speech (timestamped, though you don't see \
the timestamp), often just a clause or short phrase rather than a full sentence
- {"index": N, "marker": true} - a wordless passage (e.g. the instructor playing an instrument \
instead of talking). Never translate these, and never let a sentence group span across one.

Group consecutive speech items into complete, natural sentences, then translate each group as a \
whole into one complete, natural English sentence - do NOT force a 1:1 translation per item; \
merge as many consecutive speech items as needed to form a proper sentence. It may be casual, \
contain false starts, or minor transcription errors - work around those sensibly.

Respond with ONLY valid JSON (no markdown fences, no commentary) matching exactly this shape:

{
  "sentences": [
    {"start_index": 0, "end_index": 2, "english": "one complete, natural English sentence covering items 0 through 2"}
  ],
  "vocabulary": [
    {"turkish": "word or phrase as it appears", "english": "meaning", "note": "brief usage note, optional, can be empty string"}
  ],
  "grammar_notes": [
    {"topic": "short topic name, e.g. 'Passive voice (-il/-in)'", "explanation": "1-3 sentences, grounded in the actual word/phrase from this transcript"}
  ]
}

Critical rules for "sentences": every speech item must belong to exactly one group, listed in \
transcript order. A group's start_index/end_index must span a contiguous run of speech-item \
indices with no marker index anywhere inside that range - if a marker sits between two speech \
items, they belong to different groups even if the sentence feels unfinished. Never reorder, \
skip, or duplicate an index.
""" + _VOCAB_GRAMMAR_GUIDELINES


def _extract_usage(response) -> dict:
    usage = response.usage
    if not usage:
        return {}
    log.info(
        f"Token usage - prompt: {usage.prompt_tokens}, "
        f"completion: {usage.completion_tokens}, total: {usage.total_tokens}"
    )
    return {
        "prompt_tokens": usage.prompt_tokens,
        "completion_tokens": usage.completion_tokens,
        "total_tokens": usage.total_tokens,
    }


def _parse_json_response(content: str) -> dict:
    try:
        return json.loads(content)
    except json.JSONDecodeError as e:
        log.error(f"Model did not return valid JSON: {content[:500]}")
        raise e


def translate_freeform(segments_marked: list) -> dict:
    """
    segments_marked: [{"start", "end", "text", ["is_marker"]}, ...]
    Returns {"sentence_pairs": [{"turkish", "english"}], "vocabulary": [...],
    "grammar_notes": [...], "usage": {...}}. Pairs carry no timestamps.
    """
    turkish_text = " ".join(s["text"] for s in segments_marked)

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        temperature=0.3,
        messages=[
            {"role": "system", "content": FREEFORM_SYSTEM_PROMPT},
            {"role": "user", "content": turkish_text},
        ],
    )
    data = _parse_json_response(response.choices[0].message.content)

    data.setdefault("sentence_pairs", [])
    data.setdefault("vocabulary", [])
    data.setdefault("grammar_notes", [])
    data["usage"] = _extract_usage(response)
    return data


def _validate_and_build_groups(segments_marked: list, raw_groups: list) -> list:
    """
    Validates GPT's {"start_index", "end_index", "english"} groups against
    segments_marked and, if they check out, returns them sorted by
    start_index. Raises ValueError with a specific reason otherwise - no
    partial/best-effort recovery, since a silently misaligned group would
    produce a wrong click-to-seek timestamp.
    """
    n = len(segments_marked)
    groups = sorted(raw_groups, key=lambda g: g.get("start_index", -1))

    def skip_markers(pos: int) -> int:
        while pos < n and segments_marked[pos].get("is_marker"):
            pos += 1
        return pos

    cursor = skip_markers(0)
    for g in groups:
        start, end = g.get("start_index"), g.get("end_index")
        if not isinstance(start, int) or not isinstance(end, int) or not (0 <= start <= end < n):
            raise ValueError(f"Aligned mode: group has an invalid index range: {g}")
        if start != cursor:
            raise ValueError(
                f"Aligned mode: expected the next group to start at index {cursor} (skipping any "
                f"marker items), got {start} ({g}). Groups must cover every speech item exactly "
                "once, in order, with no gaps."
            )
        marker_indices = [i for i in range(start, end + 1) if segments_marked[i].get("is_marker")]
        if marker_indices:
            raise ValueError(
                f"Aligned mode: group {g} spans marker index/indices {marker_indices} - a "
                "sentence group must never cross a [[DEMONSTRATION]] marker."
            )
        cursor = skip_markers(end + 1)

    if cursor != n:
        raise ValueError(
            f"Aligned mode: groups covered indices up to {cursor - 1}, but speech items continue "
            f"to index {n - 1}. Some speech was dropped from the translation."
        )

    return groups


def translate_segments_aligned(segments_marked: list) -> dict:
    """
    segments_marked: [{"start", "end", "text", ["is_marker"]}, ...]
    Returns the same shape as translate_freeform, but every sentence pair
    also carries "start"/"end" (seconds): the timestamp of the first/last
    segment in its group. The Turkish side is reconstructed directly from
    the source segments (always exactly faithful); only the English side
    and the grouping itself come from GPT.
    """
    payload = [
        {"index": i, "marker": True} if s.get("is_marker") else {"index": i, "turkish": s["text"]}
        for i, s in enumerate(segments_marked)
    ]

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        temperature=0.3,
        messages=[
            {"role": "system", "content": ALIGNED_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    data = _parse_json_response(response.choices[0].message.content)
    groups = _validate_and_build_groups(segments_marked, data.get("sentences", []))

    sentence_pairs = []
    i, g = 0, 0
    while i < len(segments_marked):
        seg = segments_marked[i]
        if seg.get("is_marker"):
            sentence_pairs.append({
                "turkish": DEMONSTRATION_TOKEN, "english": DEMONSTRATION_TOKEN,
                "start": seg["start"], "end": seg["end"],
            })
            i += 1
        else:
            group = groups[g]
            turkish_text = " ".join(segments_marked[j]["text"] for j in range(group["start_index"], group["end_index"] + 1))
            sentence_pairs.append({
                "turkish": turkish_text,
                "english": group.get("english", ""),
                "start": segments_marked[group["start_index"]]["start"],
                "end": segments_marked[group["end_index"]]["end"],
            })
            i = group["end_index"] + 1
            g += 1

    return {
        "sentence_pairs": sentence_pairs,
        "vocabulary": data.get("vocabulary", []),
        "grammar_notes": data.get("grammar_notes", []),
        "usage": _extract_usage(response),
    }
