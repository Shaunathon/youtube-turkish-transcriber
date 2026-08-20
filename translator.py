"""
Sends the Turkish transcript to OpenAI's chat completions API and gets back
Turkish/English sentence pairs with timestamps.

translate(): segments_marked is first split into marker-free spans (chunks
between [[DEMONSTRATION]] markers, which is preserved as its own standalone
pair). GPT groups each span's timestamped segments into complete, natural
sentences and translates each group as a whole - so prose quality reads
naturally, while every pair still carries the timestamp of the segment it
starts at (from the first segment in its group), driving click-to-seek.
Because a span never contains a marker, "never span a marker" isn't a rule
GPT has to remember and follow - it's structurally impossible to break.
The Turkish side of each pair is reconstructed directly from the source
segments rather than trusted to GPT, so it's always exactly faithful - no
drift-checking needed.
"""
import json
import logging

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL, OUTPUT_FOLDER
from demonstration import DEMONSTRATION_TOKEN

log = logging.getLogger("youtube-transcriber")
client = OpenAI(api_key=OPENAI_API_KEY)

_MAX_ATTEMPTS = 3
# Escalate temperature on retry - two failed attempts landing on the exact
# same gap at the same low temperature suggests sampling near-identical
# completions rather than exploring genuinely different groupings.
_RETRY_TEMPERATURES = [0.3, 0.6, 0.9]

# A [[DEMONSTRATION]] marker naturally caps how many segments land in one
# grouping call, but a video with continuous talking and no long pauses can
# produce a single marker-free span covering the whole transcript. Observed
# in practice on an 83-segment span: GPT loses track near the end and
# either drops items or fabricates dozens of extra ones past the real
# range (indices up to 110 when only 83 existed) - retrying at a higher
# temperature didn't fix it, and made the fabrication worse. Capping span
# size directly addresses the actual cause (too much to track in one
# structured response) rather than hoping retries paper over it.
_MAX_SPAN_SIZE = 25

_MUSIC_TERMINOLOGY_GUIDANCE = """
Domain context: these transcripts are Turkish clarinet instruction, often covering Turkish \
makam (modal) music theory and ornamentation technique. When a Turkish word or phrase has more \
than one possible English meaning, choose whichever meaning fits clarinet playing and Turkish \
makam music theory specifically - never a generic or unrelated everyday sense of the word.

Specific terminology:
- "çarpma"/"çarpmalar" (also "çatma"/"çatmalar" in casual/dialect speech) names a grace-note \
ornament. Leave the term itself untranslated in the English text - never render it as "mordent," \
"hit," "strike," "clash," or "arpeggio." Translate the grammar around it normally: "üst \
çarpma"/"üst çatma" = "upper çarpma", "alt çarpma"/"alt çatma" = "lower çarpma", "çarpmalar" = \
"çarpmas". Treat it like a proper technical term, the same way makam names below are handled.
- Makam names (e.g. Kürdi, Hicaz, Nihavent, Rast, Hüseyni, Uşşak, Saba, Hüzzam, \
Kürdilihicazkar) are proper nouns naming a specific musical mode, not ordinary words - never \
translate them. Keep them as their standard English musicological spelling, dropping Turkish \
diacritics ("Kürdi" -> "Kurdi", etc.), and spell each one consistently throughout.
- If the instructor names or quotes a specific song or piece (e.g. its opening line, or "I'll \
play X"), keep that title in its original Turkish within the English translation rather than \
translating it - it is a proper title, not descriptive text.
"""

SYSTEM_PROMPT = """You are a Turkish-English translator helping an intermediate learner. You \
will be given one continuous stretch of a Turkish transcript from an instructional video (e.g. \
a music lesson), already split into numbered items with fixed index boundaries - {"index": N, \
"turkish": "..."}. Each item is a real segment of speech (timestamped, though you don't see the \
timestamp), often just a clause or short phrase rather than a full sentence. It may be casual, \
contain false starts, or minor transcription errors - work around those sensibly.

Group consecutive items into complete, natural sentences, then translate each group as a whole \
into one complete, natural English sentence - do NOT force a 1:1 translation per item; merge as \
many consecutive items as needed to form a proper sentence.

Even a very short or seemingly trivial item - a single word like "Şimdi." ("Now.") or "Değil." \
("Not."/"Isn't it.") - must still end up inside exactly one group, never silently dropped for \
feeling too minor to be its own sentence. Merge it into an adjacent group if that reads more \
naturally, but it must never be omitted from every group.

Respond with ONLY valid JSON (no markdown fences, no commentary) matching exactly this shape:

{
  "sentences": [
    {"start_index": 0, "end_index": 2, "english": "one complete, natural English sentence covering items 0 through 2"}
  ]
}

Critical rules for "sentences": every item must belong to exactly one group, listed in \
transcript order, covering the full range from index 0 to the last index with no gaps, no \
reordering, no duplicates. You will be told the total number of items up front. Before \
finalizing your answer, explicitly verify: walking your "sentences" array in order, each \
group's start_index must equal the previous group's end_index + 1, starting at 0 and ending \
with the final group's end_index equal to the last valid index - with no item, including the \
very first and very last, left out of every group. Omitting an item is the most common mistake \
here; double-check the full range is covered before responding, especially on longer inputs.
""" + _MUSIC_TERMINOLOGY_GUIDANCE


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
            raise ValueError(f"Group has an invalid index range: {g}")
        if start != cursor:
            raise ValueError(
                f"Expected the next group to start at index {cursor} (skipping any marker "
                f"items), got {start} ({g}). Groups must cover every speech item exactly once, "
                "in order, with no gaps."
            )
        marker_indices = [i for i in range(start, end + 1) if segments_marked[i].get("is_marker")]
        if marker_indices:
            raise ValueError(
                f"Group {g} spans marker index/indices {marker_indices} - a sentence group must "
                "never cross a [[DEMONSTRATION]] marker."
            )
        cursor = skip_markers(end + 1)

    if cursor != n:
        raise ValueError(
            f"Groups covered indices up to {cursor - 1}, but speech items continue to index "
            f"{n - 1}. Some speech was dropped from the translation."
        )

    return groups


def _write_debug_dump(payload_items: list, attempt_log: list) -> str:
    """
    Written only when every retry is exhausted, so the exact request items
    and every attempt's raw response can be inspected without needing to
    re-run (and re-pay for) Whisper + GPT to reproduce it.
    """
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)
    debug_path = OUTPUT_FOLDER / "translate_debug.json"
    debug_path.write_text(
        json.dumps({"items": payload_items, "attempts": attempt_log}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return str(debug_path)


def _split_into_spans(segments_marked: list) -> list:
    """
    Splits segments_marked into [(global_start_index, span_segments), ...].
    Markers are the first, natural boundary: a span never contains one, so
    GPT is never asked to reason about markers at all, eliminating "a group
    illegally spans a marker" as a possible mistake rather than relying on
    a prompt rule to prevent it. Any resulting span longer than
    _MAX_SPAN_SIZE is then further cut into consecutive same-size chunks -
    unlike marker boundaries, this split doesn't need a "reason" the model
    has to respect; consecutive segments translated via separate calls
    still read naturally in sequence, just as more (smaller, more
    reliably-tracked) requests instead of one large one.
    """
    raw_spans = []
    current, current_start = [], None
    for i, s in enumerate(segments_marked):
        if s.get("is_marker"):
            if current:
                raw_spans.append((current_start, current))
                current, current_start = [], None
        else:
            if not current:
                current_start = i
            current.append(s)
    if current:
        raw_spans.append((current_start, current))

    spans = []
    for start, segs in raw_spans:
        for offset in range(0, len(segs), _MAX_SPAN_SIZE):
            spans.append((start + offset, segs[offset:offset + _MAX_SPAN_SIZE]))
    return spans


def _group_span(span_segments: list) -> tuple:
    """
    Calls GPT to group one marker-free span into complete sentences with
    translations, retrying with escalating temperature on validation
    failure (GPT occasionally drops an item, more often on longer spans).
    Returns (groups, usage_dict). Raises ValueError (after writing a debug
    dump) if every retry fails.
    """
    payload_items = [{"index": i, "turkish": s["text"]} for i, s in enumerate(span_segments)]
    user_content = json.dumps(
        {"total_items": len(payload_items), "items": payload_items}, ensure_ascii=False
    )

    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    data = groups = last_error = None
    attempt_log = []
    for attempt in range(1, _MAX_ATTEMPTS + 1):
        temperature = _RETRY_TEMPERATURES[min(attempt - 1, len(_RETRY_TEMPERATURES) - 1)]
        response = client.chat.completions.create(
            model=OPENAI_MODEL,
            response_format={"type": "json_object"},
            temperature=temperature,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
        )
        for key, value in _extract_usage(response).items():
            usage_total[key] = usage_total.get(key, 0) + value

        data = _parse_json_response(response.choices[0].message.content)
        attempt_record = {"attempt": attempt, "temperature": temperature, "response": data}
        attempt_log.append(attempt_record)
        try:
            groups = _validate_and_build_groups(span_segments, data.get("sentences", []))
            break
        except ValueError as e:
            last_error = e
            attempt_record["error"] = str(e)
            log.warning(
                f"Span grouping attempt {attempt}/{_MAX_ATTEMPTS} "
                f"(temperature {temperature}) failed validation: {e}"
            )
    else:
        debug_path = _write_debug_dump(payload_items, attempt_log)
        raise ValueError(
            f"GPT's segment grouping failed validation {_MAX_ATTEMPTS} times in a row for one "
            f"span. Last error: {last_error}\n"
            f"Full request items and every attempt's raw response were written to {debug_path} "
            "for troubleshooting, so this doesn't need to be reproduced by re-running Whisper."
        )

    return groups, usage_total


def translate(segments_marked: list) -> dict:
    """
    segments_marked: [{"start", "end", "text", ["is_marker"]}, ...]
    Returns {"sentence_pairs": [{"turkish", "english", "start", "end"}],
    "usage": {...}}. "start"/"end" (seconds) is the timestamp of the
    first/last segment in the pair's group. The Turkish side is
    reconstructed directly from the source segments (always exactly
    faithful); only the English side and the grouping itself come from
    GPT, one marker-free span at a time.
    """
    spans = _split_into_spans(segments_marked)

    sentence_pairs = []
    usage_total = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    span_index = 0
    i = 0
    while i < len(segments_marked):
        seg = segments_marked[i]
        if seg.get("is_marker"):
            sentence_pairs.append({
                "turkish": DEMONSTRATION_TOKEN, "english": DEMONSTRATION_TOKEN,
                "start": seg["start"], "end": seg["end"],
            })
            i += 1
            continue

        global_start, span_segments = spans[span_index]
        if global_start != i:
            raise RuntimeError(f"Internal error: span/segment walk out of sync ({global_start} != {i}).")

        groups, usage = _group_span(span_segments)
        for key, value in usage.items():
            usage_total[key] = usage_total.get(key, 0) + value

        for group in groups:
            g_start = global_start + group["start_index"]
            g_end = global_start + group["end_index"]
            turkish_text = " ".join(segments_marked[j]["text"] for j in range(g_start, g_end + 1))
            sentence_pairs.append({
                "turkish": turkish_text,
                "english": group.get("english", ""),
                "start": segments_marked[g_start]["start"],
                "end": segments_marked[g_end]["end"],
            })

        i = global_start + len(span_segments)
        span_index += 1

    return {
        "sentence_pairs": sentence_pairs,
        "usage": usage_total,
    }
