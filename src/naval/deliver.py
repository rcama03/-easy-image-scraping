"""Prepare a finished video for GitHub delivery.

GitHub rejects files over 100MB, so videos bigger than that are split
into 95MB parts (final.mp4.part00, part01, ...). To rebuild the video
after downloading the parts:

    Linux/Mac:   cat final.mp4.part* > final.mp4
    Windows:     copy /b final.mp4.part00+final.mp4.part01 final.mp4

Usage:
    python -m src.naval.deliver output/ep1/final.mp4 deliveries/ep1
"""
import argparse
import shutil
from pathlib import Path

PART_SIZE = 95 * 1024 * 1024


def prepare(video: Path, dest_dir: Path):
    dest_dir.mkdir(parents=True, exist_ok=True)
    size = video.stat().st_size
    if size <= PART_SIZE:
        dest = dest_dir / video.name
        shutil.copy2(video, dest)
        print(f"{video.name}: {size / 1e6:.0f}MB, fits as a single file -> {dest}")
        return [dest]
    parts = []
    with open(video, "rb") as f:
        idx = 0
        while chunk := f.read(PART_SIZE):
            part = dest_dir / f"{video.name}.part{idx:02d}"
            part.write_bytes(chunk)
            parts.append(part)
            print(f"  wrote {part.name} ({len(chunk) / 1e6:.0f}MB)")
            idx += 1
    readme = dest_dir / "HOW_TO_REBUILD.txt"
    readme.write_text(
        f"{video.name} was split for GitHub's 100MB file limit.\n\n"
        f"Download all {len(parts)} parts into one folder, then run:\n\n"
        f"  Linux/Mac:  cat {video.name}.part* > {video.name}\n"
        f"  Windows:    copy /b "
        + "+".join(p.name for p in parts) + f" {video.name}\n"
    )
    print(f"{video.name}: {size / 1e6:.0f}MB split into {len(parts)} parts")
    return parts + [readme]


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("video", type=Path)
    p.add_argument("dest", type=Path)
    args = p.parse_args()
    prepare(args.video, args.dest)


if __name__ == "__main__":
    main()
