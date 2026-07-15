"""Hand-curated public-domain archival footage for naval episodes.

Automated footage scraping is unreliable for this genre (licence ambiguity +
segment selection), so clips are curated by hand: pick a public-domain source
(US federal government / National Archives films are PD by 17 USC 105; captured
enemy WWII film held by NARA is PD), find a good segment, and conform it to the
channel's look — 1920x1080 @ 25fps, black & white to match the stills.

A footage clip then drops into the pipeline exactly where a scraped still would,
occupying the same narration time-slot (looped/trimmed to the slide duration).
"""
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TIMEOUT = 600
FPS = 25


def _run(cmd, what):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}):\n{p.stderr[-800:]}")


def ia_url(identifier: str, filename: str) -> str:
    """Direct download URL for a file inside an Internet Archive item."""
    from urllib.parse import quote
    return f"https://archive.org/download/{identifier}/{quote(filename)}"


def probe_frames(src: str, seconds, out_dir: Path):
    """Grab a single frame at each timestamp so a segment can be chosen by eye
    (footage review, same idea as the image contact sheets). Streams via range
    requests — no full download."""
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for s in seconds:
        dst = out_dir / f"t{int(s):05d}.jpg"
        cmd = [FFMPEG, "-y", "-ss", str(s), "-i", src, "-frames:v", "1",
               "-vf", "scale=480:-1", str(dst)]
        try:
            _run(cmd, f"probe {s}s")
            paths.append(dst)
        except Exception:
            pass
    return paths


def make_clip(src: str, dst: Path, start: float, dur: float, bw: bool = True):
    """Extract [start, start+dur] and conform to 1920x1080@25fps (B&W to match
    the documentary stills). Letterbox-pads so nothing is cropped."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    vf = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
          "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=" + str(FPS))
    if bw:
        vf += ",hue=s=0"
    cmd = [FFMPEG, "-y", "-ss", f"{start:.2f}", "-i", src, "-t", f"{dur:.2f}",
           "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-pix_fmt", "yuv420p", str(dst)]
    _run(cmd, f"clip {dst.name}")
    return dst
