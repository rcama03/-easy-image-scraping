"""Requests-based image URL sources (no browser needed).

Each source function takes (query, max_results) and returns a list of
direct image URLs. Sources fail soft: on any error they return [] so the
pipeline can fall through to the next engine.

For British naval history, Wikimedia Commons and Wikipedia page images are
listed first on purpose: they are high resolution and overwhelmingly public
domain, which matters for YouTube monetisation.
"""
import json
import re
import urllib.parse

import requests

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Accept-Language": "en-GB,en;q=0.9",
}
TIMEOUT = 20


def wikimedia_commons(query: str, max_results: int = 8):
    """Search Wikimedia Commons files, return scaled (max 1920px) image URLs."""
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrsearch": query,
        "gsrnamespace": 6, "gsrlimit": max_results * 2,
        "prop": "imageinfo", "iiprop": "url|size|mime",
        "iiurlwidth": 1920,
    }
    try:
        r = requests.get("https://commons.wikimedia.org/w/api.php",
                         params=params, headers=HEADERS, timeout=TIMEOUT)
        pages = r.json().get("query", {}).get("pages", {})
        urls = []
        for page in sorted(pages.values(), key=lambda p: p.get("index", 99)):
            for info in page.get("imageinfo", []):
                if info.get("mime", "").startswith("image/") and info.get("width", 0) >= 640:
                    urls.append(info.get("thumburl") or info["url"])
        return urls[:max_results]
    except Exception:
        return []


def wikipedia_pageimage(query: str, max_results: int = 2):
    """Lead image of the best-matching Wikipedia article (great for portraits)."""
    try:
        r = requests.get("https://en.wikipedia.org/w/api.php", params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": query, "gsrlimit": max(max_results, 3),
            "prop": "pageimages", "piprop": "original",
        }, headers=HEADERS, timeout=TIMEOUT)
        pages = r.json().get("query", {}).get("pages", {})
        # 'index' is the search rank — without sorting, dict order can put a
        # loosely related article (e.g. the admiral's wife) first
        ranked = sorted(pages.values(), key=lambda p: p.get("index", 99))
        return [p["original"]["source"] for p in ranked
                if "original" in p][:max_results]
    except Exception:
        return []


def bing_images(query: str, max_results: int = 10):
    """Parse direct image URLs out of the Bing image search HTML."""
    try:
        r = requests.get(
            "https://www.bing.com/images/search",
            params={"q": query, "form": "HDRSC2", "first": 1},
            headers=HEADERS, timeout=TIMEOUT,
        )
        urls = re.findall(r'murl&quot;:&quot;(.*?)&quot;', r.text)
        if not urls:  # layout without HTML-encoded JSON
            urls = re.findall(r'"murl":"(.*?)"', r.text)
        seen, out = set(), []
        for u in urls:
            u = u.encode().decode("unicode_escape")
            if u.startswith("http") and u not in seen:
                seen.add(u)
                out.append(u)
        return out[:max_results]
    except Exception:
        return []


def duckduckgo_images(query: str, max_results: int = 10):
    """DuckDuckGo image API: fetch vqd token, then query i.js."""
    try:
        s = requests.Session()
        s.headers.update(HEADERS)
        page = s.get("https://duckduckgo.com/",
                     params={"q": query, "iax": "images", "ia": "images"},
                     timeout=TIMEOUT)
        m = re.search(r'vqd=[\'"]?([\d-]+)', page.text)
        if not m:
            return []
        r = s.get("https://duckduckgo.com/i.js", params={
            "l": "us-en", "o": "json", "q": query, "vqd": m.group(1),
            "f": ",,,", "p": "1",
        }, headers={**HEADERS, "Referer": "https://duckduckgo.com/"},
            timeout=TIMEOUT)
        results = json.loads(r.text).get("results", [])
        return [x["image"] for x in results if x.get("image")][:max_results]
    except Exception:
        return []


SOURCES = {
    "wikimedia": wikimedia_commons,
    "wikipedia": wikipedia_pageimage,
    "bing": bing_images,
    "duckduckgo": duckduckgo_images,
}
DEFAULT_ORDER = ["wikipedia", "wikimedia", "bing", "duckduckgo"]

# Stock photo agencies watermark their previews — never use them.
WATERMARK_DOMAINS = (
    "alamy", "gettyimages", "shutterstock", "istockphoto", "dreamstime",
    "123rf", "bigstockphoto", "depositphotos", "agefotostock", "stock.adobe",
    "bridgemanimages", "granger", "mediastorehouse", "superstock",
    "photos.com", "fineartamerica", "posterlounge", "meisterdrucke",
    "artuk.org", "prints-online", "watermark",
)


def _watermarked(url: str) -> bool:
    host = urllib.parse.urlparse(url).netloc.lower()
    return any(d in host for d in WATERMARK_DOMAINS)


def commons_title_from_url(url: str) -> str | None:
    """Recover the Commons file title from an upload.wikimedia.org URL so its
    licence + author can be looked up for attribution. Thumbnails embed the
    original file name after '/thumb/'."""
    m = re.search(r"/(?:commons|wikipedia/[a-z-]+)/(?:thumb/)?[0-9a-f]/[0-9a-f]{2}/([^/]+)", url)
    if not m:
        return None
    name = urllib.parse.unquote(m.group(1))
    return "File:" + name


def collect_urls(query: str, per_source: int = 6, order=None,
                 wiki_query: str | None = None):
    """Query every source in order, return de-duplicated URLs (source-tagged).

    wiki_query: exact entity name for Wikipedia/Commons (their search ranks
    the plain name best), while the padded query goes to the web engines.
    """
    seen, results = set(), []
    for name in order or DEFAULT_ORDER:
        fn = SOURCES.get(name)
        if fn is None:
            continue
        q = wiki_query if wiki_query and name in ("wikipedia", "wikimedia") else query
        for url in fn(q, per_source):
            if _watermarked(url):
                continue
            key = urllib.parse.urlparse(url)._replace(query="").geturl()
            if key not in seen:
                seen.add(key)
                results.append((name, url))
    return results
