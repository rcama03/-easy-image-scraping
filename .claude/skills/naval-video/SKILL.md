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
- Video length == audio length, joint audio+video fade-out at the end.
  No sudden voiceover cut.
- Maximum quality; only downsize if the file would exceed 3 GitHub parts
  (285MB) — `ensure_max_size` handles this automatically. Never more
  than 3 parts.
- Typical episodes are 13–22 minutes. The whole job must finish within
  ~1 hour; never poll or wait without a timeout. Run the pipeline with
  Bash run_in_background + a Monitor on the log for milestones/errors.

## Steps

1. Install deps if needed: `pip install -r requirements.txt faster-whisper`.
   Convert .docx scripts to .txt first if necessary.
2. Build a curated entity list — auto-extraction alone is too sparse for
   long episodes. Target roughly one slide per 25–35s of audio (~30
   slides for 15 min). Write a small generator (see the pattern in the
   Warspite episode: anchor phrase in script → name/kind/query) that
   locates each anchor's `first_pos` in the script and saves
   `entities.json`. Include every ship, person, battle AND supporting
   visuals (places, weapons, aircraft). For Wikipedia accuracy use exact
   article names (e.g. "HMS Hardy (H87)", "German destroyer Erich Giese").
3. Run the pipeline (from the repo root, in background, with a Monitor):

   ```
   python -m src.naval.pipeline \
       --script <script.txt> --audio <voiceover> \
       --entities <curated entities.json> \
       --timings <timings.json if provided> \
       --out output/<episode-slug>
   ```

4. While it renders, visually spot-check several framed slides (Read the
   jpg) — especially people (portrait searches often return relatives or
   group photos) and generic queries. A wrong image can be fixed
   mid-render by overwriting `framed/NNN_*.jpg` with an alternate IF the
   clip renderer hasn't reached that slide yet (check the log); otherwise
   re-render just that portion. Also check the era is right (e.g. the
   1940 battleship Warspite, not the 1827 sailing ship of the same name).
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
