"""
Sends the Turkish transcript to OpenAI's chat completions API and gets back
Turkish/English sentence pairs plus vocabulary and grammar notes.

Two modes, chosen by main.py based on the --click-to-seek flag:

- translate_freeform: GPT freely resplits the whole transcript into
  natural, flowing sentences. Reads best, but the resulting pairs carry no
  timestamps.
- translate_segments_aligned: GPT translates each Whisper/caption segment
  in place, one-to-one, so every pair keeps its real timestamp and can
  drive click-to-seek. Segments are often shorter than full sentences, so
  this reads choppier - that's the tradeoff being tested.

Both preserve [[DEMONSTRATION]] markers verbatim rather than translating
them.
"""
import difflib
import json
import logging

from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from demonstration import DEMONSTRATION_TOKEN

log = logging.getLogger("youtube-transcriber")
client = OpenAI(api_key=OPENAI_API_KEY)

_NOTES_GUIDELINES = """
Guidelines:
- vocabulary: 5-12 words/phrases genuinely worth learning for an intermediate learner. Skip \
trivial ones (ve, bir, bu) unless the usage is notable (idiom, unusual case, etc).
- grammar_notes: 2-6 structures actually present in this transcript (suffixes, tenses, cases, \
particles, word order). Quote the relevant word or phrase from the transcript itself rather \
than giving a generic textbook explanation.
- If the transcript is very short, it is fine to return fewer vocabulary/grammar/sentence items.
- The literal token [[DEMONSTRATION]] may appear in the transcript, marking a wordless passage \
(e.g. the instructor playing an instrument instead of talking). It is not Turkish - never \
translate it, explain it, or treat it as vocabulary/grammar. Leave it exactly as-is wherever \
it must appear in your output.
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
""" + _NOTES_GUIDELINES

ALIGNED_SYSTEM_PROMPT = """You are a Turkish-English translator and language tutor helping an \
intermediate learner. You will be given a Turkish transcript from an instructional video (e.g. \
a music lesson), already split into numbered fragments with fixed boundaries - each fragment is \
a real segment of speech (from timestamps you don't see), sometimes a full sentence, often \
just a clause or phrase. It may be casual, contain false starts, or minor transcription errors - \
work around those sensibly.

Respond with ONLY valid JSON (no markdown fences, no commentary) matching exactly this shape:

{
  "segment_translations": [
    {"index": 0, "english": "English translation of fragment 0"}
  ],
  "vocabulary": [
    {"turkish": "word or phrase as it appears", "english": "meaning", "note": "brief usage note, optional, can be empty string"}
  ],
  "grammar_notes": [
    {"topic": "short topic name, e.g. 'Passive voice (-il/-in)'", "explanation": "1-3 sentences, grounded in the actual word/phrase from this transcript"}
  ]
}

Critical rule for segment_translations: you MUST return exactly one entry per input fragment, \
with the same index, in the same order - never merge two fragments into one translation, never \
split one fragment into two, never reorder, never add or drop a fragment. Use the surrounding \
fragments as context for meaning, but the boundary of each translation must match the boundary \
of its source fragment exactly, even if that makes a given English fragment read as an \
incomplete or awkward clause on its own - reliable fragment-to-fragment alignment matters more \
here than smooth prose.
""" + _NOTES_GUIDELINES


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


def _check_sentence_drift(original: str, sentence_pairs: list) -> None:
    """Sanity check only - logs a warning, doesn't block anything."""
    reconstructed = " ".join(p.get("turkish", "") for p in sentence_pairs)
    a = " ".join(original.split())
    b = " ".join(reconstructed.split())
    if not a or not b:
        return
    ratio = difflib.SequenceMatcher(None, a, b).ratio()
    if ratio < 0.85:
        log.warning(
            f"Sentence segmentation drifted from the original transcript (similarity {ratio:.0%}) "
            "- hover highlighting may be slightly off."
        )


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
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        log.error(f"Model did not return valid JSON: {content[:500]}")
        raise e

    data.setdefault("sentence_pairs", [])
    data.setdefault("vocabulary", [])
    data.setdefault("grammar_notes", [])
    _check_sentence_drift(turkish_text, data["sentence_pairs"])
    data["usage"] = _extract_usage(response)
    return data


def translate_segments_aligned(segments_marked: list) -> dict:
    """
    segments_marked: [{"start", "end", "text", ["is_marker"]}, ...]
    Returns the same shape as translate_freeform, but every sentence pair
    also carries "start"/"end" (seconds) from its source segment, and pair
    boundaries exactly match the input segments rather than GPT-chosen
    sentence breaks.
    """
    real = [(i, s) for i, s in enumerate(segments_marked) if not s.get("is_marker")]
    fragments_payload = [{"index": i, "turkish": s["text"]} for i, s in real]

    response = client.chat.completions.create(
        model=OPENAI_MODEL,
        response_format={"type": "json_object"},
        temperature=0.3,
        messages=[
            {"role": "system", "content": ALIGNED_SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(fragments_payload, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content
    try:
        data = json.loads(content)
    except json.JSONDecodeError as e:
        log.error(f"Model did not return valid JSON: {content[:500]}")
        raise e

    translations = {t["index"]: t.get("english", "") for t in data.get("segment_translations", [])}
    missing = [i for i, _ in real if i not in translations]
    if missing:
        raise ValueError(
            f"Model returned {len(translations)} segment translations but {len(real)} were "
            f"requested (missing indices: {missing[:10]}{'...' if len(missing) > 10 else ''}). "
            "Aligned mode requires an exact 1:1 match to keep timestamps correct - not proceeding "
            "with a partial/misaligned result."
        )

    sentence_pairs = []
    for i, s in enumerate(segments_marked):
        if s.get("is_marker"):
            sentence_pairs.append({
                "turkish": DEMONSTRATION_TOKEN, "english": DEMONSTRATION_TOKEN,
                "start": s["start"], "end": s["end"],
            })
        else:
            sentence_pairs.append({
                "turkish": s["text"], "english": translations[i],
                "start": s["start"], "end": s["end"],
            })

    return {
        "sentence_pairs": sentence_pairs,
        "vocabulary": data.get("vocabulary", []),
        "grammar_notes": data.get("grammar_notes", []),
        "usage": _extract_usage(response),
    }
