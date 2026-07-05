"""Compose a source image onto a clean 1920x1080 frame (no text).

Blurred, darkened fill in the background so vertical portraits get no
black pillar-boxes; sharp image fitted on top. Optional black & white
conversion for the classic history-documentary look.
"""
from pathlib import Path

from PIL import Image, ImageFilter, ImageOps

FRAME_W, FRAME_H = 1920, 1080


def _fit(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = min(w / img.width, h / img.height)
    return img.resize((max(1, int(img.width * scale)),
                       max(1, int(img.height * scale))), Image.LANCZOS)


def _fill(img: Image.Image, w: int, h: int) -> Image.Image:
    scale = max(w / img.width, h / img.height)
    img = img.resize((int(img.width * scale) + 1, int(img.height * scale) + 1),
                     Image.LANCZOS)
    left, top = (img.width - w) // 2, (img.height - h) // 2
    return img.crop((left, top, left + w, top + h))


def frame_image(src: Path, dst: Path, bw: bool = True) -> Path:
    img = Image.open(src).convert("RGB")
    if bw:
        img = ImageOps.autocontrast(img.convert("L"), cutoff=1).convert("RGB")

    bg = _fill(img, FRAME_W, FRAME_H).filter(ImageFilter.GaussianBlur(30))
    bg = Image.eval(bg, lambda px: int(px * 0.40))

    fg = _fit(img, FRAME_W, FRAME_H)
    frame = bg
    frame.paste(fg, ((FRAME_W - fg.width) // 2, (FRAME_H - fg.height) // 2))

    dst.parent.mkdir(parents=True, exist_ok=True)
    frame.save(dst, "JPEG", quality=95)
    return dst
