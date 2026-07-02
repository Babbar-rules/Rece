"""Download up to N images per dish.

Sources, in priority order:
  1. Wikidata P18 image (Wikimedia Commons, openly licensed)
  2. TheMealDB thumbnail (when a recipe matched)
  3. Wikimedia Commons search by dish name (openly licensed)

We only pull from openly-licensed sources to keep the repo redistributable.
"""
from __future__ import annotations

from pathlib import Path

from .common import (IMAGES_DIR, RateLimiter, download_file, get_json,
                     make_session)

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 4

# Wikimedia bot policy wants a modest rate. ~1.1s between calls keeps us well
# under their threshold and avoids 429s on upload.wikimedia.org.
_limiter = RateLimiter(1.1)


def _commons_search(session, term: str, need: int) -> list[str]:
    """Return direct image URLs from Commons matching `term`."""
    data = get_json(
        session, COMMONS_API,
        params={
            "action": "query", "format": "json", "generator": "search",
            "gsrsearch": f'filetype:bitmap {term}', "gsrnamespace": 6,
            "gsrlimit": need, "prop": "imageinfo",
            "iiprop": "url", "iiurlwidth": 1024,
        },
        limiter=_limiter,
    )
    urls = []
    if data:
        for page in data.get("query", {}).get("pages", {}).values():
            info = page.get("imageinfo", [{}])[0]
            url = info.get("thumburl") or info.get("url")
            if url:
                urls.append(url)
    return urls


def download_images(slug: str, name: str, wikidata_image: str,
                    mealdb_thumb: str) -> list[str]:
    """Download <=4 images into data/images/<slug>/. Return relative paths."""
    dest = IMAGES_DIR / slug
    dest.mkdir(parents=True, exist_ok=True)
    session = make_session()

    candidates: list[str] = []
    if wikidata_image:
        candidates.append(wikidata_image)
    if mealdb_thumb:
        candidates.append(mealdb_thumb)
    if len(candidates) < MAX_IMAGES:
        candidates += _commons_search(session, name, MAX_IMAGES - len(candidates))

    saved: list[str] = []
    seen: set[str] = set()
    for url in candidates:
        if len(saved) >= MAX_IMAGES or url in seen:
            continue
        seen.add(url)
        ext = Path(url.split("?")[0]).suffix.lower() or ".jpg"
        if ext not in (".jpg", ".jpeg", ".png", ".webp", ".gif"):
            ext = ".jpg"
        out = dest / f"{slug}-{len(saved) + 1}{ext}"
        if download_file(session, url, out, limiter=_limiter):
            saved.append(str(out.relative_to(IMAGES_DIR.parent).as_posix()))
    return saved
