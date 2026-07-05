"""Render a source image onto a 1920x1080 frame with a caption lower-third.

The frame is filled with a blurred, darkened copy of the image so portraits
(vertical) do not get black pillar-boxes; the sharp image is fitted on top,
and the caption is drawn on a gradient band at the bottom.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

FRAME_W, FRAME_H = 1920, 1080
FONT_PATH = "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf"
FONT_PATH_SUB = "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf"


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


def caption_image(src: Path, dst: Path, caption: str, subcaption: str = ""):
    img = Image.open(src).convert("RGB")

    # blurred background fill, darkened
    bg = _fill(img, FRAME_W, FRAME_H).filter(ImageFilter.GaussianBlur(28))
    bg = Image.eval(bg, lambda px: int(px * 0.45))

    # sharp foreground, leaving room for the caption band
    fg = _fit(img, FRAME_W - 160, FRAME_H - 200)
    frame = bg
    frame.paste(fg, ((FRAME_W - fg.width) // 2, (FRAME_H - 160 - fg.height) // 2 + 30))

    # bottom gradient band
    band = Image.new("L", (1, 260), 0)
    for y in range(260):
        band.putpixel((0, y), int(235 * (y / 260) ** 1.5))
    band = band.resize((FRAME_W, 260))
    black = Image.new("RGB", (FRAME_W, 260), (0, 0, 0))
    frame.paste(Image.composite(black, frame.crop((0, FRAME_H - 260, FRAME_W, FRAME_H)), band),
                (0, FRAME_H - 260))

    draw = ImageDraw.Draw(frame)
    font = ImageFont.truetype(FONT_PATH, 56)
    while draw.textlength(caption, font=font) > FRAME_W - 240 and font.size > 28:
        font = ImageFont.truetype(FONT_PATH, font.size - 4)
    y = FRAME_H - 150
    draw.text((FRAME_W // 2, y), caption, font=font, fill=(245, 240, 225),
              anchor="mm", stroke_width=2, stroke_fill=(0, 0, 0))
    if subcaption:
        sub = ImageFont.truetype(FONT_PATH_SUB, 34)
        draw.text((FRAME_W // 2, y + 62), subcaption, font=sub,
                  fill=(200, 195, 180), anchor="mm")

    dst.parent.mkdir(parents=True, exist_ok=True)
    frame.save(dst, "JPEG", quality=92)
    return dst
