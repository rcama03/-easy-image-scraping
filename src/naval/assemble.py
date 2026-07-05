"""Assemble captioned slides + narration audio into a draft MP4.

Uses the static ffmpeg binary shipped by imageio-ffmpeg, so no system
ffmpeg install is required. Slides are spread evenly across the audio
duration (or 6s each if no audio is given). Optional Ken Burns zoom.
"""
import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()


def audio_duration(path: Path) -> float:
    proc = subprocess.run([FFMPEG, "-i", str(path)],
                          capture_output=True, text=True)
    m = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", proc.stderr)
    if not m:
        raise RuntimeError(f"Could not read duration of {path}")
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def assemble_video(slides, audio: Path | None, out: Path,
                   fps: int = 25, kenburns: bool = True, log=print):
    """slides: ordered list of image paths."""
    if not slides:
        raise ValueError("No slides to assemble")
    total = audio_duration(audio) if audio else len(slides) * 6.0
    per_slide = total / len(slides)
    log(f"  {len(slides)} slides x {per_slide:.1f}s = {total:.0f}s total")

    tmp = out.parent / "_clips"
    tmp.mkdir(parents=True, exist_ok=True)
    clips = []
    frames = max(1, int(per_slide * fps))
    for i, slide in enumerate(slides):
        clip = tmp / f"clip_{i:03d}.mp4"
        if kenburns:
            # slow push-in; upscale first so zoompan doesn't jitter
            vf = (f"scale=3840:2160,zoompan=z='1+0.10*on/{frames}':"
                  f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                  f"d={frames}:s=1920x1080:fps={fps}")
            cmd = [FFMPEG, "-y", "-loop", "1", "-i", str(slide),
                   "-vf", vf, "-frames:v", str(frames),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)]
        else:
            cmd = [FFMPEG, "-y", "-loop", "1", "-t", f"{per_slide:.3f}",
                   "-i", str(slide), "-vf", "scale=1920:1080", "-r", str(fps),
                   "-c:v", "libx264", "-pix_fmt", "yuv420p", str(clip)]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise RuntimeError(f"ffmpeg failed on slide {slide}:\n{proc.stderr[-800:]}")
        clips.append(clip)
        log(f"  clip {i + 1}/{len(slides)} done")

    concat_file = tmp / "concat.txt"
    concat_file.write_text("".join(f"file '{c.resolve()}'\n" for c in clips))
    cmd = [FFMPEG, "-y", "-f", "concat", "-safe", "0", "-i", str(concat_file)]
    if audio:
        cmd += ["-i", str(audio), "-map", "0:v", "-map", "1:a",
                "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "copy", str(out)]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg concat failed:\n{proc.stderr[-800:]}")
    log(f"  wrote {out}")
    return out
