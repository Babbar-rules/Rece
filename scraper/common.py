"""Shared helpers: HTTP session, rate limiting, slugs, paths."""
from __future__ import annotations

import re
import time
import unicodedata
from pathlib import Path

import requests

# Be a polite bot. Wikimedia REQUIRES a descriptive User-Agent with a real
# contact; a vague UA gets 429'd aggressively. Set a valid contact here.
USER_AGENT = (
    "WorldDishesScraper/1.0 "
    "(https://github.com/Babbar-rules/Rece; godfathertheme1@gmail.com) requests"
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


def _retry_after(resp, attempt: int) -> float:
    """Seconds to wait after a 429/503, honoring the Retry-After header."""
    ra = resp.headers.get("Retry-After") if resp is not None else None
    if ra:
        try:
            return min(float(ra), 120.0)
        except ValueError:
            pass
    return min(5 * (2 ** attempt), 120.0)  # exponential backoff, capped


def get_json(session: requests.Session, url: str, *, params=None,
             limiter: RateLimiter | None = None, retries: int = 5):
    """GET JSON with retry/backoff. Returns parsed JSON or None."""
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        try:
            r = session.get(url, params=params, timeout=45)
            if r.status_code in (429, 503):
                time.sleep(_retry_after(r, attempt))
                continue
            r.raise_for_status()
            return r.json()
        except (requests.RequestException, ValueError) as exc:
            if attempt == retries - 1:
                print(f"  ! request failed: {url} -> {exc}")
                return None
            time.sleep(2 * (attempt + 1))
    return None


def download_file(session: requests.Session, url: str, dest,
                  *, limiter: RateLimiter | None = None, retries: int = 5) -> bool:
    """Download a binary file with 429/503 retry + backoff. True on success."""
    for attempt in range(retries):
        if limiter:
            limiter.wait()
        try:
            r = session.get(url, timeout=60, stream=True)
            if r.status_code in (429, 503):
                r.close()
                time.sleep(_retry_after(r, attempt))
                continue
            r.raise_for_status()
            with open(dest, "wb") as fh:
                for chunk in r.iter_content(8192):
                    fh.write(chunk)
            return True
        except requests.RequestException as exc:
            if attempt == retries - 1:
                print(f"    ! image failed {url}: {exc}")
                return False
            time.sleep(2 * (attempt + 1))
    return False


def slugify(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    text = re.sub(r"[\s_-]+", "-", text)
    return text or "dish"
