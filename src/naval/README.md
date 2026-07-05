# Naval History Video Pipeline

Turns a narration script (and optionally its voice-over audio) into
caption-ready visuals for a British naval history channel:

1. **Extract entities** from the script — people (by rank/title), ships
   (`HMS ...`), battles (`Battle of ...`) — in narration order.
2. **Scrape images** per entity from Wikipedia page images, Wikimedia
   Commons, Bing Images and DuckDuckGo (requests only, no browser).
   Wikipedia/Commons are queried first: for this genre they give the
   highest resolution images and are mostly public domain, which is the
   safest option for monetised YouTube videos.
3. **Caption** each image onto a 1920x1080 frame: blurred-fill background,
   sharp fitted image, name rendered on a bottom gradient band.
4. **Assemble** a draft MP4: slides spread evenly across the narration
   audio, with a slow Ken Burns push-in.

## Usage

```shell
pip install -r requirements.txt

python -m src.naval.pipeline \
    --script data/scripts/episode1.txt \
    --audio  data/audio/episode1.mp3 \
    --out    output/episode1
```

Output layout:

```
output/episode1/
  entities.json           # what was detected — edit and re-run if needed
  raw/<entity>/           # all downloaded candidates per entity
  captioned/NNN_*.jpg     # one slide per entity, numbered in narration order
  captioned/alternates/   # captioned alternate images, easy to swap in
  draft.mp4               # slides timed across the audio
```

## Useful flags

| Flag | Effect |
|---|---|
| `--entities out/entities.json` | re-run from a hand-corrected entity list |
| `--keep 6` | keep more candidate images per entity |
| `--engines bing,duckduckgo` | change source order / restrict sources |
| `--no-video` | captioned images only |
| `--no-kenburns` | static slides (renders much faster) |

## Fixing a wrong image

Open `captioned/alternates/`, pick the better shot, and rename it over the
main `captioned/NNN_*.jpg` slide — or edit `entities.json` (change the
`query`) and re-run with `--entities`. Then re-run with `--no-video`
removed to rebuild `draft.mp4`.
