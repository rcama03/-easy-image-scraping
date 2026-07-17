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
import requests

from src.naval.sources import HEADERS

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
TIMEOUT = 600
FPS = 25
VIDEO_MIMES = ("video/webm", "video/mp4", "video/ogg", "application/ogg")


def _run(cmd, what):
    p = subprocess.run(cmd, capture_output=True, text=True, timeout=TIMEOUT)
    if p.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}):\n{p.stderr[-800:]}")


def ia_url(identifier: str, filename: str) -> str:
    """Direct download URL for a file inside an Internet Archive item."""
    from urllib.parse import quote
    return f"https://archive.org/download/{identifier}/{quote(filename)}"


def commons_videos(query: str, max_results: int = 6):
    """Search Wikimedia Commons for free (PD/CC) video files matching `query`.
    Commons federates archival film from many national archives, all under
    free licences. Returns [(url, file_title), ...]; file_title feeds
    attribution.commons_credit for the description credits."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json",
            "generator": "search", "gsrsearch": f"{query} filetype:video",
            "gsrnamespace": 6, "gsrlimit": max_results * 2,
            "prop": "imageinfo", "iiprop": "url|mime|size",
        }, headers=HEADERS, timeout=30)
        pages = r.json().get("query", {}).get("pages", {})
        out = []
        for p in sorted(pages.values(), key=lambda x: x.get("index", 99)):
            ii = (p.get("imageinfo") or [{}])[0]
            if ii.get("mime") in VIDEO_MIMES and ii.get("url"):
                out.append((ii["url"], p.get("title", "")))
        return out[:max_results]
    except Exception:
        return []


def ia_footage(query: str, max_results: int = 6, watermark_terms=("periscope",)):
    """Search Internet Archive movingimage for public-domain / CC footage.
    Skips items whose uploader is known to burn watermarks. Returns
    [(identifier, title), ...] — resolve a downloadable file via the item's
    metadata API before handing the URL to make_clip."""
    try:
        r = requests.get("https://archive.org/advancedsearch.php", params={
            "q": (f'({query}) AND mediatype:movies AND '
                  '(licenseurl:*creativecommons* OR '
                  'rights:*public* OR collection:(FedFlix OR usgovfilms OR '
                  'nara OR prelinger))'),
            "fl[]": "identifier,title,uploader",
            "rows": max_results * 2, "output": "json",
        }, headers=HEADERS, timeout=30)
        docs = r.json().get("response", {}).get("docs", [])
        out = []
        for d in docs:
            up = (d.get("uploader") or "").lower()
            if any(w in up for w in watermark_terms):
                continue  # reseller watermark — unsafe for monetisation
            out.append((d["identifier"], d.get("title", "")))
        return out[:max_results]
    except Exception:
        return []


def ia_playable_file(identifier: str):
    """Pick a downloadable video file from an IA item's metadata (the direct
    /download/ URL 500s without the real server+dir). Returns a full URL or
    None."""
    try:
        r = requests.get(f"https://archive.org/metadata/{identifier}",
                         headers=HEADERS, timeout=30)
        meta = r.json()
        server = meta.get("server")
        d = meta.get("dir")
        best = None
        for f in meta.get("files", []):
            name = f.get("name", "")
            if name.lower().endswith((".mp4", ".mpeg", ".mpg", ".mov",
                                      ".m4v", ".ogv", ".webm")):
                size = int(f.get("size", 0) or 0)
                if best is None or size > best[0]:
                    best = (size, name)
        if not (server and d and best):
            return None
        from urllib.parse import quote
        return f"https://{server}{d}/{quote(best[1])}"
    except Exception:
        return None


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
          "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,setsar=1,fps=" + str(FPS))
    if bw:
        vf += ",hue=s=0"
    cmd = [FFMPEG, "-y", "-ss", f"{start:.2f}", "-i", src, "-t", f"{dur:.2f}",
           "-vf", vf, "-an", "-c:v", "libx264", "-preset", "veryfast",
           "-crf", "16", "-pix_fmt", "yuv420p", str(dst)]
    _run(cmd, f"clip {dst.name}")
    return dst
