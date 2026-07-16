"""Licence + attribution capture for every reused asset.

We only source free/open assets — Public Domain, CC0, CC-BY, CC-BY-SA — from
Wikimedia Commons (which federates the German Bundesarchiv, Archives New
Zealand, IWM public-domain photos, the US National Archives and many more) and
from Internet Archive public-domain / Creative-Commons films.

For CC-BY / CC-BY-SA the licence requires attribution, so the pipeline records
author + licence + source URL for each file actually used and writes a
credits.md the channel can paste into the video description. Nothing is burned
on screen.
"""
import re
import html
import requests

from src.naval.sources import HEADERS

FREE_LICENCES = ("public domain", "pd", "cc0", "cc-by", "cc by", "cc-by-sa",
                 "cc by-sa", "attribution")


def _clean(v: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", v or "")).strip()


def commons_credit(file_title: str) -> dict | None:
    """Fetch licence + author for a Commons file (e.g. 'File:Foo.jpg').
    Returns {title, author, licence, licence_url, source_url} or None."""
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php", params={
            "action": "query", "format": "json", "prop": "imageinfo",
            "iiprop": "extmetadata|url", "titles": file_title,
        }, headers=HEADERS, timeout=20)
        pages = r.json().get("query", {}).get("pages", {})
        for p in pages.values():
            ii = (p.get("imageinfo") or [{}])[0]
            em = ii.get("extmetadata", {})
            lic = _clean(em.get("LicenseShortName", {}).get("value", ""))
            if not lic:
                return None
            return {
                "title": _clean(em.get("ObjectName", {}).get("value", ""))
                         or p.get("title", "").replace("File:", ""),
                "author": _clean(em.get("Artist", {}).get("value", ""))
                          or _clean(em.get("Credit", {}).get("value", "")),
                "licence": lic,
                "licence_url": em.get("LicenseUrl", {}).get("value", ""),
                "source_url": ii.get("descriptionurl", ""),
            }
    except Exception:
        return None
    return None


def is_free(licence: str) -> bool:
    l = (licence or "").lower()
    return any(k in l for k in FREE_LICENCES)


def write_credits(entries, out_path):
    """entries: list of dicts (title, author, licence, source_url, [extra]).
    Writes a de-duplicated, licence-grouped credits.md for the description."""
    seen, rows = set(), []
    for e in entries:
        key = (e.get("source_url") or e.get("title", ""))
        if key in seen:
            continue
        seen.add(key)
        rows.append(e)
    lines = ["IMAGE & FOOTAGE CREDITS", ""]
    lines.append("All assets below are Public Domain or Creative Commons "
                 "(CC0 / CC-BY / CC-BY-SA). Attribution as required:\n")
    for e in sorted(rows, key=lambda r: r.get("licence", "")):
        who = e.get("author") or "Unknown"
        lines.append(f"- “{e.get('title','')}” — {who} — "
                     f"{e.get('licence','')} — {e.get('source_url','')}")
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path
