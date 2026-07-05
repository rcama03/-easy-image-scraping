"""End-to-end pipeline: script -> entities -> scraped images -> captioned
slides -> draft video.

Usage:
    python -m src.naval.pipeline --script data/scripts/ep1.txt \
        --audio data/audio/ep1.mp3 --out output/ep1

Outputs under --out:
    entities.json          extracted entities (edit + re-run with --entities)
    raw/<entity>/*.jpg     all downloaded candidates per entity
    captioned/NNN_*.jpg    one captioned 1920x1080 slide per entity, in
                           narration order (drop-in for any video editor)
    draft.mp4              slides timed evenly across the narration audio
"""
import argparse
import re
from pathlib import Path

from src.naval.assemble import assemble_video
from src.naval.caption import caption_image
from src.naval.download import download_entity_images
from src.naval.entities import extract_entities, load_entities, save_entities


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def run(script: Path | None, audio: Path | None, out: Path,
        entities_file: Path | None = None, keep: int = 4,
        engines: list[str] | None = None, make_video: bool = True,
        kenburns: bool = True):
    out.mkdir(parents=True, exist_ok=True)

    if entities_file:
        entities = load_entities(entities_file)
        print(f"Loaded {len(entities)} entities from {entities_file}")
    else:
        text = script.read_text(encoding="utf-8", errors="replace")
        entities = extract_entities(text)
        print(f"Extracted {len(entities)} entities from {script}:")
        for e in entities:
            print(f"  [{e.kind:6}] {e.name}  ({e.mentions} mentions)")
    save_entities(entities, out / "entities.json")

    slides = []
    for i, entity in enumerate(entities):
        print(f"({i + 1}/{len(entities)}) scraping: {entity.name}")
        images = download_entity_images(
            entity, out / "raw" / slug(entity.name), keep=keep, order=engines)
        if not images:
            continue
        dst = out / "captioned" / f"{i:03d}_{slug(entity.name)}.jpg"
        caption_image(images[0], dst, entity.caption)
        # caption the alternates too, so swapping in an editor is trivial
        for j, alt in enumerate(images[1:], start=1):
            caption_image(alt, out / "captioned" / "alternates" /
                          f"{i:03d}_{slug(entity.name)}_alt{j}.jpg",
                          entity.caption)
        slides.append(dst)

    print(f"\n{len(slides)} captioned slides in {out / 'captioned'}")

    if make_video and slides:
        print("Assembling draft video...")
        assemble_video(slides, audio, out / "draft.mp4", kenburns=kenburns)
    return slides


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--script", type=Path, help="narration script (.txt)")
    p.add_argument("--audio", type=Path, help="narration audio (mp3/wav/m4a)")
    p.add_argument("--out", type=Path, required=True, help="output folder")
    p.add_argument("--entities", type=Path,
                   help="use an edited entities.json instead of re-extracting")
    p.add_argument("--keep", type=int, default=4,
                   help="images to keep per entity (default 4)")
    p.add_argument("--engines", type=str,
                   help="comma list: wikipedia,wikimedia,bing,duckduckgo")
    p.add_argument("--no-video", action="store_true")
    p.add_argument("--no-kenburns", action="store_true",
                   help="static slides instead of slow zoom (much faster)")
    args = p.parse_args()

    if not args.script and not args.entities:
        p.error("need --script or --entities")

    run(args.script, args.audio, args.out,
        entities_file=args.entities, keep=args.keep,
        engines=args.engines.split(",") if args.engines else None,
        make_video=not args.no_video, kenburns=not args.no_kenburns)


if __name__ == "__main__":
    main()
