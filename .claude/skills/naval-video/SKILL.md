---
name: naval-video
description: Produce a finished British naval history video from an uploaded narration script and voiceover audio — scrape B&W images, karaoke subtitles, assemble, deliver via chat + GitHub. Use whenever the user uploads a script/audio for an episode or says "naval video", "make my video", or similar.
---

# Naval Video Workflow

Turn the user's uploaded narration script (.txt/.docx) and voiceover audio
(mp3/wav/m4a) into a finished YouTube-ready video using the pipeline in
`src/naval/` of this repository.

## Fixed channel rules (do not ask again)

- Images: black & white, no watermarks (stock domains are blocklisted),
  scraped from Wikipedia/Wikimedia first, then Bing/DuckDuckGo.
- NO captions/text burned onto the images themselves.
- Narration subtitles in Reise-Insider style: bold UPPERCASE sans-serif,
  bottom center, white, current spoken word highlighted yellow (this is
  what `src/naval/subtitles.py` produces — do not restyle).
- Slides change when their person/ship/battle is mentioned; if no image
  was found for an entity, the previous image stays on screen. Never a
  blank clip.
- Video length == audio length, joint audio+video fade-out at the end.
  No sudden voiceover cut.
- Maximum quality; only downsize if the file would exceed 3 GitHub parts
  (285MB) — `ensure_max_size` handles this automatically.
- Typical episodes are 13–22 minutes. The whole job must finish within
  ~1 hour; never poll or wait without a timeout.

## Steps

1. Install deps if needed: `pip install -r requirements.txt faster-whisper`.
   Convert .docx scripts to .txt first if necessary.
2. Run the pipeline (from the repo root):

   ```
   python -m src.naval.pipeline \
       --script <script.txt> --audio <voiceover> --out output/<episode-slug>
   ```

3. Review `output/<slug>/entities.json` and spot-check 2–3 framed slides
   visually (Read the jpg). If an image is clearly wrong, fix its `query`
   in entities.json and re-run with `--entities`.
4. Verify the result: extract 2 frames from `final.mp4` and confirm
   subtitles + B&W images look right; confirm duration matches the audio.
5. Deliver — BOTH of these, always:
   - Send `final.mp4` in chat with SendUserFile (display: attach).
   - Copy it to `deliveries/<episode-slug>/` (run
     `python -m src.naval.deliver output/<slug>/final.mp4 deliveries/<slug>`
     which splits >95MB files into max 3 parts), commit, push, and give
     the user the direct download link(s):
     `https://github.com/rcama03/-easy-image-scraping/raw/<branch>/deliveries/<slug>/<file>`
6. Also commit `entities.json` and the framed slides folder so the user
   can re-edit later. Do NOT commit `raw/` candidates or `_clips/`.

## Troubleshooting

- Karaoke subs empty → audio may have no detectable speech; retry with
  `--whisper-model small.en`.
- A scrape source hanging or erroring → sources fail soft; if overall
  scraping is slow, restrict with `--engines wikipedia,wikimedia,bing`.
- Render too slow for the 1-hour budget → add `--no-kenburns` (static
  slides) which is several times faster.
