"""Download up to N images per dish.

Sources, in priority order:
  1. Wikidata P18 image (Wikimedia Commons, openly licensed)
  2. TheMealDB thumbnail (when a recipe matched)
  3. Wikimedia Commons search by dish name (openly licensed)

We only pull from openly-licensed sources to keep the repo redistributable.
"""
from __future__ import annotations

from pathlib import Path

from .common import IMAGES_DIR, RateLimiter, get_json, make_session

COMMONS_API = "https://commons.wikimedia.org/w/api.php"
MAX_IMAGES = 4

_limiter = RateLimiter(0.5)


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
        try:
            _limiter.wait()
            r = session.get(url, timeout=45, stream=True)
            r.raise_for_status()
            with open(out, "wb") as fh:
                for chunk in r.iter_content(8192):
                    fh.write(chunk)
            saved.append(str(out.relative_to(IMAGES_DIR.parent).as_posix()))
        except Exception as exc:  # noqa: BLE001 - keep scraping on any failure
            print(f"    ! image failed {url}: {exc}")
    return saved
