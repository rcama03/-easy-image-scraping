# Naval Video Pipeline — Summary

A complete `/naval-video` pipeline that turns a narration script + voiceover
into a finished, captioned British naval-history YouTube video.

- Code: `src/naval/`
- Reusable skill: `.claude/skills/naval-video/SKILL.md`
- Deliveries: `deliveries/<episode-slug>/`

## Episodes delivered
1. **HMS Warspite / 2nd Battle of Narvik** (`deliveries/warspite-narvik/`) — iterated v1→v4
2. **HMS Upholder / Armando Diaz** (`deliveries/hms-upholder/`) — review / dedup / spacing
3. **Battle of Cape Spada** (`deliveries/cape-spada/`) — 57 slides, 524 MB, 6 parts

## Inputs (one uploaded ZIP)
Script (`.txt`), voiceover `.mp3`, `timings.json`, `captions.srt`,
9 infographic PNGs, 2 intro clips (named `1` / `2`).

## Complete feature list (every rule)

### Images
- Exhaustive coverage — **1 slide per ~12–17 s** (~60 slides/episode); every
  named ship, person, place, nation, navy/force, battle, event, incident,
  weapon, aircraft, institution gets a slide.
- **Black & white**, "slightly lighter" documentary look
  (brightness 1.12 / bg 0.50 in `frames.py`).
- Sources: Wikipedia/Wikimedia first, then Bing/DuckDuckGo.
  **Watermark stock domains blocklisted.**
- **No text burned onto images.**
- **Global duplicate guard** — the same photo never appears on two slides.
- Missing image → previous slide holds (never a blank clip).

### User infographics
- Placed at their exact narration beat, kept in **full colour**.
- **Never two-in-a-row** — `space_user_slides` inserts a scraped image between
  them, keeping the same time-slots so pacing/length are unchanged.

### User intro clips
- Conformed to 1080p25, their own audio dropped, played **over the first
  ~20 s** of narration; total video length stays locked to the audio length.

### Captions (Reise-Insider karaoke style)
- Bold UPPERCASE sans-serif, bottom centre, white with the currently-spoken
  word highlighted **yellow**.
- Timed to the **actual audio** (whisper transcription + `align_words`), NOT
  the raw `timings.json` (used only for exact word spellings — its raw times
  drift and are never trusted).
- **No overlapping/stacked captions** (monotonic timestamps + end-clamp);
  over-long lines auto-shrink so they never touch the frame edges.

### Output
- Video length == audio length, **joint audio+video fade-out** at the end.
- **Maximum quality, NEVER re-encoded to shrink.**
- Master split into as many **95 MB GitHub parts** as needed.

### Workflow safeguards
- **Mandatory numbered contact sheets** (`write_contact_sheets` →
  `<out>/contact_sheets/review_*.jpg`) sent to the user for review **before
  rendering**; the user flags irrelevant/repeated slides by number.
- **Never render without the user's explicit typed "render".**
- Full visual QC of every slide before assembly (portraits / namesakes /
  wrong-era images are the scraper's weak spots).
- Runs in background + Monitor; hard timeouts everywhere; **finishes within
  ~1 hour.**

### Delivery
- GitHub part links + a `copy /b` rejoin command (Windows):
  `copy /b file.mp4.part00+file.mp4.part01+... file.mp4`
  (Linux/Mac: `cat file.mp4.part* > file.mp4`).
- Full MP4 also attached in chat **only if under 30 MB**; larger episodes
  (~500 MB) are delivered as GitHub parts only.
- Large videos are pushed in **2-part batches** to avoid large-push failures.

## Modules (`src/naval/`)
| File | Role |
|---|---|
| `entities.py` | `Entity` dataclass (name/kind/query/first_pos/`image`/`color`); heuristic extractor |
| `sources.py` | image sources (Wikipedia, Wikimedia, Bing, DuckDuckGo) + watermark blocklist |
| `download.py` | per-entity download, filter, de-dup |
| `frames.py` | 1920x1080 framing, B&W + brightness, blurred-fill background |
| `subtitles.py` | whisper transcription, `align_words`, karaoke `.ass`, overlap/长line fixes |
| `contact.py` | `write_contact_sheets` — numbered review sheets |
| `assemble.py` | `space_user_slides`, Ken Burns clips, intro conform, final encode, fades |
| `deliver.py` | split master into 95 MB parts + rebuild instructions |
| `pipeline.py` | end-to-end CLI orchestration |

## Run
```
python -m src.naval.pipeline \
    --script <script.txt> --audio <voiceover.mp3> \
    --entities <entities.json> --timings <timings.json> \
    --intro <1.mp4,2.mp4> --out output/<slug>
```
Useful flags: `--no-video`, `--no-subs`, `--no-kenburns`, `--color`,
`--engines wikipedia,wikimedia,bing`, `--whisper-model small.en`.

## Gotchas learned
- Reading many/large images into the agent's own context fails
  ("request too large") on long conversations → send contact sheets to the
  user, read images one at a time.
- `/plugin` is unavailable in the Claude-Code-on-web environment.
- Chat attachment limit 30 MB; GitHub file limit 100 MB/part.
