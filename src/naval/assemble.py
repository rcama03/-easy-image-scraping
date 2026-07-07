"""Assemble framed slides + narration audio into the final MP4.

Rules (channel spec):
  - slide changes follow the narration: each slide starts when its entity
    is mentioned; if an entity had no usable image the previous slide
    simply stays on screen (never a blank clip)
  - video length == audio length exactly; both fade out together at the
    end (no sudden voice-over cut, no trailing black)
  - Reise-Insider style karaoke subtitles burned in (optional .ass file)
  - high quality: CRF 16 x264, 256k AAC — no size squeezing

Uses the static ffmpeg binary from imageio-ffmpeg (libass included).
Every subprocess has a timeout so the pipeline can never hang.
"""
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
CLIP_TIMEOUT = 600       # s per slide clip
FINAL_TIMEOUT = 2400     # s for the final encode
MIN_SLIDE = 2.0          # s minimum a slide stays on screen
FADE = 2.5               # s fade-out at the very end
FPS = 25


def _run(cmd, timeout, what):
    proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg failed ({what}):\n{proc.stderr[-800:]}")
    return proc


def audio_duration(path: Path) -> float:
    proc = subprocess.run([FFMPEG, "-i", str(path)],
                          capture_output=True, text=True, timeout=60)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", proc.stderr)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def schedule_slides(slides_with_pos, total: float, offset: float = 0.0):
    """slides_with_pos: [(path, narration_fraction 0..1), ...] in order.
    Returns [(path, duration), ...] covering [offset, total] with no gaps
    (offset > 0 when intro animation clips occupy the start)."""
    starts = []
    for i, (path, frac) in enumerate(slides_with_pos):
        start = (offset if i == 0
                 else max(frac * total, starts[-1][1] + MIN_SLIDE, offset))
        starts.append((path, start))
    # drop slides pushed past the end
    starts = [(p, s) for p, s in starts if s < total - MIN_SLIDE or s == 0.0]
    out = []
    for i, (path, start) in enumerate(starts):
        end = starts[i + 1][1] if i + 1 < len(starts) else total
        out.append((path, end - start))
    return out


def space_user_slides(slides):
    """Break up runs of consecutive user images (infographics) so no two
    sit back-to-back — channel rule: there must always be a scraped image
    between them (the infographic is nudged just before/after its beat).

    slides: [(path, frac, is_user), ...] in narration order.
    Returns [(path, frac), ...] — the SAME time-slots (sorted fracs) are
    kept, so pacing and total length are unchanged; only which image
    occupies each slot is locally reshuffled, so every image still lands
    within a slot or two of its narration moment.
    """
    n = len(slides)
    slots = sorted(f for _, f, _ in slides)
    used = [False] * n
    order = []
    for j in range(n):
        if used[j]:
            continue
        path, frac, is_user = slides[j]
        if is_user and order and order[-1][2]:
            # last placed was also a user image → insert a scraped separator
            k = next((k for k in range(j + 1, n)
                      if not used[k] and not slides[k][2]), None)
            if k is None:  # no scraped left ahead: take any unused
                k = next((k for k in range(j + 1, n) if not used[k]), None)
            if k is not None:
                order.append(slides[k])
                used[k] = True
        order.append(slides[j])
        used[j] = True
    return [(p, slots[i]) for i, (p, _, _) in enumerate(order)]


def _render_clip(slide: Path, duration: float, clip: Path, kenburns: bool):
    frames = max(1, round(duration * FPS))
    if kenburns:
        vf = (f"scale=2880:1620,zoompan=z='1+0.09*on/{frames}':"
              f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
              f"d={frames}:s=1920x1080:fps={FPS}")
        cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(slide),
               "-vf", vf, "-frames:v", str(frames),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
               "-pix_fmt", "yuv420p", str(clip)]
    else:
        cmd = [FFMPEG, "-y", "-loop", "1", "-t", f"{duration:.3f}",
               "-i", str(slide), "-vf", "scale=1920:1080", "-r", str(FPS),
               "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
               "-pix_fmt", "yuv420p", str(clip)]
    _run(cmd, CLIP_TIMEOUT, f"clip {slide.name}")


def _conform_intro(src: Path, dst: Path):
    """Conform a user animation clip to 1920x1080@FPS, drop its audio
    (the narration plays underneath). Returns the clip duration."""
    vf = ("scale=1920:1080:force_original_aspect_ratio=decrease,"
          "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black,fps=" + str(FPS))
    cmd = [FFMPEG, "-y", "-i", str(src), "-vf", vf, "-an",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "14",
           "-pix_fmt", "yuv420p", str(dst)]
    _run(cmd, CLIP_TIMEOUT, f"intro {src.name}")
    return audio_duration(dst)


def assemble_video(slides_with_pos, audio: Path, out: Path,
                   subtitles: Path | None = None,
                   kenburns: bool = True, intros=None, log=print):
    if not slides_with_pos:
        raise ValueError("No slides to assemble")
    total = audio_duration(audio)

    tmp = out.parent / "_clips"
    tmp.mkdir(parents=True, exist_ok=True)

    # user animation clips play over the START of the narration; the video
    # length stays locked to the audio length
    intro_clips, intro_total = [], 0.0
    for k, intro in enumerate(intros or []):
        clip = tmp / f"intro_{k}.mp4"
        d = _conform_intro(Path(intro), clip)
        intro_clips.append(clip)
        intro_total += d
        log(f"  intro {k + 1}: {Path(intro).name} ({d:.1f}s)")
    if intro_total > total * 0.5:
        raise ValueError(f"Intro clips ({intro_total:.0f}s) cover more than "
                         f"half the narration ({total:.0f}s) — refusing")

    timed = schedule_slides(slides_with_pos, total, offset=intro_total)
    log(f"  {len(timed)} slides over {total:.0f}s (narration-timed)")

    clips = list(intro_clips)
    for i, (slide, duration) in enumerate(timed):
        clip = tmp / f"clip_{i:03d}.mp4"
        _render_clip(Path(slide), duration, clip, kenburns)
        clips.append(clip)
        log(f"  clip {i + 1}/{len(timed)} ({duration:.1f}s) done")

    concat_file = tmp / "concat.txt"
    concat_file.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))

    fade_start = max(0.0, total - FADE)
    vf_parts = []
    if subtitles:
        # escape for the subtitles filter (colon + quote rules)
        sub = str(Path(subtitles).resolve()).replace("\\", "/").replace(":", r"\:")
        vf_parts.append(f"subtitles=filename='{sub}'")
    vf_parts.append(f"fade=t=in:st=0:d=0.6,fade=t=out:st={fade_start:.2f}:d={FADE}")
    cmd = [FFMPEG, "-y",
           "-f", "concat", "-safe", "0", "-i", str(concat_file),
           "-i", str(audio),
           "-map", "0:v", "-map", "1:a",
           "-vf", ",".join(vf_parts),
           "-af", f"afade=t=out:st={fade_start:.2f}:d={FADE}",
           "-t", f"{total:.3f}",
           "-c:v", "libx264", "-preset", "medium", "-crf", "16",
           "-pix_fmt", "yuv420p",
           "-c:a", "aac", "-b:a", "256k",
           "-movflags", "+faststart",
           str(out)]
    log("  final encode (subtitles + fades) ...")
    _run(cmd, FINAL_TIMEOUT, "final encode")
    log(f"  wrote {out}")
    # per user rule: never re-encode to shrink — deliver full quality,
    # split into as many GitHub parts as needed
    return out


MAX_DELIVERY_MB = 280   # only used if ensure_max_size is called explicitly


def ensure_max_size(video: Path, max_mb: int = MAX_DELIVERY_MB, log=print):
    """If the encode exceeds the 3-part delivery cap, re-encode the video
    stream at the highest bitrate that still fits (audio untouched)."""
    size_mb = video.stat().st_size / 1e6
    if size_mb <= max_mb:
        return video
    total = audio_duration(video)
    audio_kbps = 256
    video_kbps = int((max_mb * 8000 * 0.97) / total) - audio_kbps
    log(f"  {size_mb:.0f}MB exceeds {max_mb}MB cap -> "
        f"re-encoding at {video_kbps}k")
    tmp = video.with_suffix(".fit.mp4")
    cmd = [FFMPEG, "-y", "-i", str(video),
           "-c:v", "libx264", "-preset", "medium",
           "-b:v", f"{video_kbps}k", "-maxrate", f"{int(video_kbps * 1.3)}k",
           "-bufsize", f"{video_kbps * 2}k", "-pix_fmt", "yuv420p",
           "-c:a", "copy", "-movflags", "+faststart", str(tmp)]
    _run(cmd, FINAL_TIMEOUT, "size-cap re-encode")
    tmp.replace(video)
    log(f"  final size {video.stat().st_size / 1e6:.0f}MB")
    return video
