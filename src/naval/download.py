"""Download candidate images for an entity, filter and de-duplicate."""
import hashlib
import io
from pathlib import Path

import requests
from PIL import Image

from src.naval.sources import HEADERS, collect_urls

MIN_WIDTH = 640
MIN_HEIGHT = 480


def download_entity_images(entity, out_dir: Path, keep: int = 4,
                           per_source: int = 6, order=None, log=print):
    """Fetch images for one entity. Returns list of saved file paths,
    best (largest, source-preferred) first."""
    out_dir.mkdir(parents=True, exist_ok=True)
    saved, hashes = [], set()
    for source, url in collect_urls(entity.query, per_source, order,
                                    wiki_query=entity.name):
        if len(saved) >= keep:
            break
        try:
            resp = requests.get(url, headers=HEADERS, timeout=25)
            content = resp.content
            digest = hashlib.sha1(content).hexdigest()[:12]
            if digest in hashes:
                continue
            img = Image.open(io.BytesIO(content))
            img.load()
            if img.width < MIN_WIDTH or img.height < MIN_HEIGHT:
                continue
            path = out_dir / f"{source}_{digest}.jpg"
            img.convert("RGB").save(path, "JPEG", quality=92)
            hashes.add(digest)
            saved.append(path)
            log(f"    [{source}] {img.width}x{img.height} -> {path.name}")
        except Exception:
            continue
    if not saved:
        log(f"    WARNING: no usable image found for '{entity.name}'")
    return saved
