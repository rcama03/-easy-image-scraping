"""Labelled contact sheets of the slide sequence, in narration order.

Emitted automatically by the pipeline so the whole image sequence can be
reviewed at a glance (12 thumbnails per sheet, numbered #1..#N) before the
final video is assembled.
"""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
TW, TH, COLS, ROWS = 560, 315, 3, 4   # 12 thumbs / sheet


def write_contact_sheets(slide_paths, out_dir: Path):
    out_dir.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype(FONT, 26)
    sheets = []
    per = COLS * ROWS
    for s in range((len(slide_paths) + per - 1) // per):
        chunk = slide_paths[s * per:(s + 1) * per]
        sheet = Image.new("RGB", (COLS * (TW + 10) + 10, ROWS * (TH + 46) + 10),
                          (18, 18, 18))
        d = ImageDraw.Draw(sheet)
        for k, p in enumerate(chunk):
            seq = s * per + k + 1
            x = 10 + (k % COLS) * (TW + 10)
            y = 10 + (k // COLS) * (TH + 46)
            try:
                sheet.paste(Image.open(p).resize((TW, TH)), (x, y))
            except Exception:
                continue
            name = Path(p).stem.split("_", 1)[-1][:36]
            d.text((x + 6, y + TH + 8), f"#{seq}  {name}", font=font,
                   fill=(255, 220, 80))
        dst = out_dir / f"review_{s}.jpg"
        sheet.save(dst, quality=90)
        sheets.append(dst)
    return sheets
