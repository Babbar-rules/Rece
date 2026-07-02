"""Shared helpers: HTTP session, rate limiting, slugs, paths."""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

import requests

# Be a polite bot. Wikidata/Wikimedia require a descriptive User-Agent.
USER_AGENT = (
    "WorldDishesScraper/1.0 "
    "(https://github.com/; contact via repo issues) requests"
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
DISHES_DIR = DATA_DIR / "dishes"
IMAGES_DIR = DATA_DIR / "images"
STATE_FILE = DATA_DIR / "state.json"

for _d in (DISHES_DIR, IMAGES_DIR):
    _d.mkdir(parents=True, exist_ok=True)


class RateLimiter:
    """Simple minimum-interval limiter, per host."""

    def __init__(self, min_interval: float):
        self.min_interval = min_interval
        self._last = 0.0

    def wait(self) -> None:
        elapsed = time.monotonic() - self._last
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last = time.monotonic()


def make_session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    return s


def get_json(session: requests.Session, url: str, *, params=None,
             limiter: RateLimiter | None = None, retries: int = 4):
    """GET JSON with retry/backoff. Returns parsed JSON or None."""
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        try:
            r = session.get(url, params=params, timeout=45)
            if r.status_code == 429:
                time.sleep(5 * (attempt + 1))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries - 1:
                print(f"  ! request failed: {url} -> {exc}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "dish"
