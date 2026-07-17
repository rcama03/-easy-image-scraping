---
name: naval-video
description: Produce a finished British naval history video from an uploaded narration script and voiceover audio — scrape B&W images, karaoke subtitles, assemble, deliver via chat + GitHub. Use whenever the user uploads a script/audio for an episode or says "naval video", "make my video", or similar.
---

# Naval Video Workflow

Turn the user's uploaded narration script (.txt/.docx) and voiceover audio
(mp3/wav/m4a) into a finished YouTube-ready video using the pipeline in
`src/naval/` of this repository.

## Fixed channel rules (do not ask again)

- Images: black & white, "slightly lighter" documentary look (the
  brightness 1.12 / bg 0.50 defaults in `frames.py` — user-approved, do
  not change without asking). No watermarks (stock domains blocklisted).
  Wikipedia/Wikimedia first, then Bing/DuckDuckGo.
- NO captions/text burned onto the images themselves.
- Narration subtitles in Reise-Insider style: bold UPPERCASE sans-serif,
  bottom center, white, current spoken word highlighted yellow (this is
  what `src/naval/subtitles.py` produces — do not restyle).
- Caption sync comes from the ACTUAL audio: whisper transcribes the
  voice-over and the script's exact words are aligned onto those timings
  (`align_words`). If the user uploads a TTS `timings.json`, pass it via
  `--timings` — it supplies exact word spellings, but its raw times are
  NEVER trusted directly (TTS timings usually predate the music mix and
  drift by seconds, unevenly).
- Slides change when their person/ship/battle is mentioned; if no image
  was found for an entity, the previous image stays on screen. Never a
  blank clip.
- User-provided images (maps, geography, etc.): the user uploads them
  with ANY filenames — you must Read each image yourself, identify what
  it shows, and place it at the matching narration moment (entity entry
  with `image` set to the file path). User images KEEP their original
  colour (`color: true`) — only scraped photos are B&W. Show the user
  your placement plan (image -> narration moment) for approval BEFORE
  rendering.
- Infographics/user images must NEVER appear two-in-a-row — a scraped
  image always sits between them (the pipeline's `space_user_slides`
  enforces this automatically; an infographic may shift just before/
  after its beat to make room). Do not defeat it.
- The pipeline always writes numbered contact sheets to
  `<out>/contact_sheets/review_*.jpg` (via `write_contact_sheets`).
  ALWAYS send these to the user with SendUserFile for review before the
  final render, so they can flag irrelevant/repeated images by number.
- OPENING (user rule, 2026-07): do NOT use user-supplied animation
  intro clips any more — they looked the same across episodes and hurt
  retention. The user will not provide them. Instead OPEN every video
  with found archival footage (the same public-domain B&W clips the
  footage module sources). For the very first beats pick the most
  ACTION-/WAR-oriented footage available (explosions, gunfire, ships
  under attack, combat manoeuvres) to HOOK the audience — the opening
  must never be a calm establishing shot or a still. That same hook
  clip MAY be reused later in the video wherever the script calls for
  such a combat beat (subject to the gap rule below). The `--intro`
  path still exists in the code but is no longer used by default; only
  pass `--intro` if the user explicitly hands over clips.
- FOOTAGE COVERAGE (user rule): always source the MAXIMUM number of
  suitable footage clips for the script — spread archival footage
  throughout, not just the opening. If the script does not yield enough
  distinct suitable clips, a clip may be REUSED once or twice, but only
  with a large temporal gap between repeats of the same clip (never the
  same footage twice close together). Prefer a fresh clip over a repeat
  whenever one fits the beat.
- Video length == audio length, joint audio+video fade-out at the end.
  No sudden voiceover cut.
- Maximum quality, NEVER re-encode to shrink (user rule). Deliver the
  full-quality master split into as many 95MB GitHub parts as needed —
  the user combines them locally.
- Typical episodes are 13–22 minutes. The whole job must finish within
  ~1 hour; never poll or wait without a timeout. Run the pipeline with
  Bash run_in_background + a Monitor on the log for milestones/errors.

## Steps

1. Install deps if needed: `pip install -r requirements.txt faster-whisper`.
   Convert .docx scripts to .txt first if necessary.
2. Build an EXHAUSTIVE entity list — auto-extraction alone is too
   sparse, and sparse coverage was explicit user feedback. Target one
   slide per 12–15s of audio (~60 slides for 15 min). Read the whole
   script and cover EVERY named item in these categories: ships,
   submarines, people, places/geography, nations, navies/forces/units,
   battles/events, incidents/accidents, weapons, aircraft, and key
   institutions (dockyards, headquarters). Write a small generator (see
   the ep2/Upholder pattern: anchor phrase in script → name/kind/query,
   user infographics as `image`+`color` entries in the same list) that
   locates each anchor's `first_pos` and saves `entities.json`. For
   Wikipedia accuracy use exact article names (e.g. "HMS Hardy (H87)",
   "Italian cruiser Armando Diaz"). Only things with no conceivable
   image are skipped — the previous slide covers them.
3. Run the pipeline (from the repo root, in background, with a Monitor):

   ```
   python -m src.naval.pipeline \
       --script <script.txt> --audio <voiceover> \
       --entities <curated entities.json> \
       --timings <timings.json if provided> \
       --out output/<episode-slug>
   ```

4. MANDATORY full visual review of EVERY framed slide BEFORE clips
   render (irrelevant images shipped in a delivered video was explicit
   user feedback — never again). Run the pipeline with `--no-video`
   first, then build labelled contact sheets (12 thumbs per sheet, PIL)
   and Read them; re-Read full-size any doubtful slide. Check: right
   subject, right ship/person (not a namesake, relative, piazza, or
   anime art), right era. Fix by: alternates, a targeted
   `wiki_lead(exact article title)` fetch, or DROP the slide (delete the
   framed jpg — an accurate neighbour beats a wrong image). Duplicates
   across slides are blocked automatically by the pipeline's
   used-digest guard; still watch for near-identical shots and vary
   them via alternates. Only then assemble (run assemble_video or
   re-run with cached raw/).
5. Verify the result: extract 2–3 frames from `final.mp4` at moments you
   can predict the spoken words (use the subtitles .ass), confirm the
   highlighted word matches what is being said, images look right, and
   duration equals the audio duration exactly.
6. Deliver — BOTH of these, always:
   - Send the mp4 in chat with SendUserFile (display: attach — the
     inline player does not work for this user).
   - Copy it to `deliveries/<episode-slug>/` (run
     `python -m src.naval.deliver output/<slug>/final.mp4 deliveries/<slug>`
     which splits >95MB files into max 3 parts), commit, push, and give
     the user the direct download link(s):
     `https://github.com/rcama03/-easy-image-scraping/raw/<branch>/deliveries/<slug>/<file>`
     plus simple step-by-step rejoin instructions (the user is not
     technical: folder → download parts → `cmd` in address bar →
     paste the `copy /b` command).
7. Also commit `entities.json`, `subtitles.ass` and the framed slides
   folder so the user can re-edit later. Do NOT commit `raw/` candidates
   or `_clips/`.
8. Re-renders after review feedback: reuse `output/<slug>/raw/` (no
   re-scraping) — re-frame, rebuild subs, re-assemble; see the
   `rerender.py` pattern from the Warspite episode. Always get the
   user's explicit approval (AskUserQuestion, with preview images for
   visual changes) BEFORE re-rendering — the user has asked to verify
   first, always.

## Troubleshooting

- Karaoke subs empty → audio may have no detectable speech; retry with
  `--whisper-model small.en`.
- Alignment below 50% match → falls back to raw transcription text
  automatically; check the audio language/quality.
- A scrape source hanging or erroring → sources fail soft; if overall
  scraping is slow, restrict with `--engines wikipedia,wikimedia,bing`.
- Render too slow for the 1-hour budget → add `--no-kenburns` (static
  slides) which is several times faster.
