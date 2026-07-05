"""End-to-end pipeline: script + voice-over -> scraped images -> framed
B&W slides -> final video with karaoke narration subtitles.

Usage:
    python -m src.naval.pipeline --script data/scripts/ep1.txt \
        --audio data/audio/ep1.mp3 --out output/ep1

Outputs under --out:
    entities.json          extracted entities (edit + re-run with --entities)
    raw/<entity>/*.jpg     all downloaded candidates per entity
    framed/NNN_*.jpg       clean 1920x1080 slides (no text), narration order
    subtitles.ass          word-synced karaoke subtitles from the voice-over
    final.mp4              the finished video
"""
import argparse
import re
from pathlib import Path

from src.naval.assemble import assemble_video
from src.naval.download import download_entity_images
from src.naval.entities import extract_entities, load_entities, save_entities
from src.naval.frames import frame_image
from src.naval.subtitles import make_subtitles


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")


def run(script: Path | None, audio: Path | None, out: Path,
        entities_file: Path | None = None, keep: int = 4,
        engines: list[str] | None = None, make_video: bool = True,
        kenburns: bool = True, bw: bool = True, subs: bool = True,
        whisper_model: str = "base.en", timings: Path | None = None):
    out.mkdir(parents=True, exist_ok=True)

    script_text = script.read_text(encoding="utf-8", errors="replace") if script else ""
    if entities_file:
        entities = load_entities(entities_file)
        print(f"Loaded {len(entities)} entities from {entities_file}")
    else:
        entities = extract_entities(script_text)
        print(f"Extracted {len(entities)} entities from {script}:")
        for e in entities:
            print(f"  [{e.kind:6}] {e.name}  ({e.mentions} mentions)")
    save_entities(entities, out / "entities.json")

    text_len = max(len(script_text), 1)
    slides = []  # (framed path, narration fraction)
    for i, entity in enumerate(entities):
        print(f"({i + 1}/{len(entities)}) scraping: {entity.name}")
        images = download_entity_images(
            entity, out / "raw" / slug(entity.name), keep=keep, order=engines)
        if not images:
            continue  # previous slide will simply stay on screen longer
        dst = out / "framed" / f"{i:03d}_{slug(entity.name)}.jpg"
        frame_image(images[0], dst, bw=bw)
        for j, alt in enumerate(images[1:], start=1):
            frame_image(alt, out / "framed" / "alternates" /
                        f"{i:03d}_{slug(entity.name)}_alt{j}.jpg", bw=bw)
        slides.append((dst, entity.first_pos / text_len))

    print(f"\n{len(slides)} framed slides in {out / 'framed'}")

    ass = None
    if subs and audio:
        print("Building karaoke subtitles...")
        ass = make_subtitles(audio, out / "subtitles.ass", whisper_model,
                             timings=timings)

    if make_video and slides and audio:
        print("Assembling final video...")
        assemble_video(slides, audio, out / "final.mp4",
                       subtitles=ass, kenburns=kenburns)
    return slides


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--script", type=Path, help="narration script (.txt)")
    p.add_argument("--audio", type=Path, help="voice-over audio (mp3/wav/m4a)")
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
    p.add_argument("--color", action="store_true",
                   help="keep original colours (default: black & white)")
    p.add_argument("--no-subs", action="store_true",
                   help="skip karaoke narration subtitles")
    p.add_argument("--whisper-model", default="base.en",
                   help="faster-whisper model (base.en/small.en/medium.en)")
    p.add_argument("--timings", type=Path,
                   help="word timings json [{word,start,end},...] from the "
                        "TTS tool; skips whisper transcription")
    args = p.parse_args()

    if not args.script and not args.entities:
        p.error("need --script or --entities")

    run(args.script, args.audio, args.out,
        entities_file=args.entities, keep=args.keep,
        engines=args.engines.split(",") if args.engines else None,
        make_video=not args.no_video, kenburns=not args.no_kenburns,
        bw=not args.color, subs=not args.no_subs,
        whisper_model=args.whisper_model, timings=args.timings)


if __name__ == "__main__":
    main()
