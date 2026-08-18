# YouTube Turkish Transcriber

Feed it a YouTube video link. For each one it:

1. **Checks YouTube for an existing *manually-created* Turkish transcript**. If one exists, it's used directly - no Whisper call needed. Auto-generated (ASR) captions are deliberately not used as a substitute - see "Notes & tuning" below for why.
2. **Otherwise downloads the audio** and transcribes it via the **OpenAI Whisper API**, splitting into multiple parts if the audio is too large for a single request.
3. **Marks long wordless stretches** - the instructor demonstrating on their instrument instead of talking - as `[[DEMONSTRATION]]` in the transcript. (Skipped when using an existing manual transcript that already tags non-speech passages itself, e.g. `[Müzik]` - see below.)
4. **Translates to English** and generates a vocabulary + grammar note set, using **OpenAI GPT**.
5. **Writes a side-by-side HTML report** per part, with the original YouTube video embedded so you can watch and read along on the same page.

This is a sibling project to `turkish-voice-transcriber` (same report styling), built specifically for long-form instructional video instead of short voice notes.

## 1. Prerequisites

- Python 3.9+
- **ffmpeg**, only needed for videos whose audio is too large for one Whisper request (splits it into time-bounded parts, `-c copy`, no re-encoding). Check with:

```bash
ffmpeg -version
```

If you don't have it: `brew install ffmpeg` (Mac) or see https://ffmpeg.org/download.html. Short videos transcribe fine without it.

- **Deno**, required for downloading audio at all (see "YouTube PO tokens" below). Check with `deno --version`; install with `brew install deno` if missing.

## 2. Install

```bash
cd youtube-turkish-transcriber
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 3. Let yt-dlp use your browser's YouTube session (one-time, required for Whisper fallback)

YouTube's bot-detection routinely blocks unauthenticated audio downloads (HTTP 403), even though the video plays fine in your browser. This only matters for videos with no manual Turkish transcript (where this tool needs to download audio itself); if a video already has one, this step is never invoked.

The fix that's actually proven reliable is borrowing your browser's existing YouTube session cookies - set via `YT_DLP_COOKIES_BROWSER` in `.env` (defaults to `chrome`). Nothing to install for this part; verify it works:

```bash
source venv/bin/activate
yt-dlp -f "140/251/139/bestaudio/18" --cookies-from-browser chrome --print title "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
```

The first time, macOS will likely prompt for Keychain access (to decrypt Chrome's cookie store) - approve it, and choose **"Always Allow"** so future runs of this tool don't prompt again. If that command prints the video's title with no error, you're set.

`requirements.txt` also installs `bgutil-ytdlp-pot-provider`, a secondary fallback used only if cookies aren't available (`YT_DLP_COOKIES_BROWSER=` empty, or the browser isn't found). It needs its actual token-generator component cloned separately:

```bash
git clone --depth 1 https://github.com/Brainicism/bgutil-ytdlp-pot-provider.git ~/bgutil-ytdlp-pot-provider
```

No build step - yt-dlp runs its script directly via Deno (`brew install deno` if you don't have it), on demand, per download. This part is optional if cookies are working for you.

## 4. Configure

```bash
cp .env.example .env
open -e .env
```

Add your `OPENAI_API_KEY` (from https://platform.openai.com/api-keys) - the same key works whether or not you're also running `turkish-voice-transcriber`.

## 5. Run it

```bash
source venv/bin/activate
python3 main.py "https://www.youtube.com/watch?v=XXXXXXXXXXX"
```

Accepts a full URL (`youtube.com/watch?v=...`, `youtu.be/...`, `/shorts/...`, `/embed/...`) or a bare 11-character video ID.

When it finishes, it automatically starts a local server and opens the report in your default browser - stay in that terminal and press `Ctrl+C` when you're done viewing to stop the server (the process won't exit on its own until you do). Pass `--no-serve` to skip this and just write the file, e.g. if you're scripting several videos back to back.

### Why it needs a server at all

The video embed needs `enablejsapi=1` to support click-to-seek, and YouTube's embedded player rejects that when a page is opened directly from disk (`file://...`) - you'd see a player error (e.g. "Error 153") instead of the video. That's what the auto-served browser tab avoids. If you used `--no-serve` and want to view a report later, serve it manually:

```bash
python3 -m http.server 8000 --directory transcripts
```

then open `http://localhost:8000/<report-name>.html`. (Once you publish these somewhere, e.g. GitHub Pages, this isn't an issue - it only affects opening the raw local file.)

## What you get

Each report (`transcripts/<video-title>.html`) has:

- **The original YouTube video embedded**, not a separate audio player - watch and read the transcript on the same page. YouTube's own player controls (including playback speed) are available in the embed. If a video has embedding disabled by its uploader, a "Watch on YouTube ↗" link next to the player is the fallback.
- **`[[DEMONSTRATION]]` markers** wherever there's a gap of `DEMONSTRATION_GAP_SECONDS` (default 7s) or more between spoken segments - including before the first word or after the last, so a long instrumental intro or closing demo gets flagged too. Only added when transcribing via Whisper; skipped for an existing manual transcript, which is left exactly as the uploader wrote it (including any `[Müzik]`/`[Alkış]`-style tags they already added for non-speech passages).
- **Turkish and English side by side**. Hover a sentence on either side to highlight its counterpart, same as the voice-note tool.
- **A vocabulary table and grammar notes**, as before.
- **A sidebar** listing every transcript processed so far, most recent first.

### Long videos: split into parts, never stitched

Whisper's API caps a single upload at 25MB. If a video's downloaded audio exceeds that (`MAX_AUDIO_MB` in `.env`, default 24 for headroom), it's split by ffmpeg into roughly-equal time chunks *before* transcription - each chunk gets its own Whisper call and its own report page (`...-part-1.html`, `...-part-2.html`, ...), clearly labeled "Part N of M" in the title and sidebar. Parts are **not stitched back together** - each page embeds the original video scoped to that part's time range (`start`/`end` params), so opening Part 2 drops you right into that section rather than the beginning.

This only applies when Whisper transcription is needed. Videos with an existing YouTube transcript are never chunked, since caption text has no size limit.

## Click-to-seek: an opt-in tradeoff

By default, translation is **freeform**: GPT reads the whole transcript and splits it into natural, flowing sentences - the same approach `turkish-voice-transcriber` uses. This reads smoothly, but the resulting sentence pairs carry no timestamps, so hovering highlights the matching pair but doesn't move the video.

Pass `--click-to-seek` to switch to **segment-aligned** translation instead: GPT translates each Whisper/caption segment individually, one-to-one, in place, so every pair keeps its exact timestamp - and clicking (not just hovering) a Turkish or English phrase seeks the embedded video there. The tradeoff: Whisper/caption segments are usually shorter than full sentences (often a clause or phrase), so the pairs read choppier - more phrase-by-phrase than paragraph-flow.

```bash
python3 main.py "<url>"                     # default: freeform, smooth prose, no seeking
python3 main.py "<url>" --click-to-seek      # segment-aligned, choppier, click-to-seek enabled
```

Running both against the same video writes two separate files (the second gets a `-clicktoseek` suffix) so you can open them side by side and judge the prose-quality cost for yourself. You can also flip the *default* for every run by setting `CLICK_TO_SEEK=true` in `.env`, and override it per-run with `--no-click-to-seek`.

## Notes & tuning

- **Existing-transcript detection**: uses `youtube-transcript-api` against YouTube's own caption tracks, but only accepts a *manually-created* Turkish transcript. YouTube's auto-generated (ASR) captions are skipped on purpose - they have no punctuation, inconsistent casing, and can contain raw ASR errors, which produced noticeably worse translations in testing than just running Whisper. If there's no manual transcript, it falls back to Whisper rather than using the lower-quality auto-generated one.
- **`DEMONSTRATION_GAP_SECONDS`**: lower it if short pauses aren't being flagged, raise it if normal conversational pauses are getting marked as demonstrations.
- **`SOURCE_LANGUAGE`**: defaults to `tr`; change it if you ever point this at a different language's instructional videos.
- **`WHISPER_TRANSCRIBE_MODEL` must stay `whisper-1`**: it's the only OpenAI transcription model that returns per-segment timestamps (`response_format="verbose_json"`), which both `[[DEMONSTRATION]]` detection and click-to-seek depend on.
- **Cost**: same pricing model as `turkish-voice-transcriber` - Whisper transcription (~$0.006/minute of audio) plus a small GPT translation/notes cost. A 30-minute lesson is roughly $0.20 of Whisper time plus a few cents of GPT, likely more in click-to-seek mode since each segment sends more context/output overhead than fewer, longer freeform sentences.
- **Temporary files**: downloaded audio (and its chunks, if split) is deleted after each successful run; nothing but the HTML report and shared assets stays in `transcripts/`.
- **Audio-only downloads aren't always available**: if YouTube blocks audio-only streams outright for a given video/session, this tool falls back to the smallest available combined video+audio stream (≤360p) instead of failing - fine for Whisper (it only needs the audio track), just a somewhat larger/slower temporary download than pure audio would be.
- **`YT_DLP_COOKIES_BROWSER`**: which browser's YouTube session cookies authorize audio downloads (default `chrome`). Set to empty to disable and rely solely on the PO-token plugin instead - only do this if cookies aren't working for you, since cookies have proven the more reliable path.

## What's not included (yet)

No `publish.py` / GitHub Pages workflow like `turkish-voice-transcriber` has - these reports currently live locally only. If you want the same "choose what to publish" flow for these, it's a small addition and worth asking for once you've used the tool a bit.
