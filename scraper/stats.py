"""Compute dataset stats and write data/stats.json + a Markdown summary.

Used by the workflow to show progress in the GitHub run summary and to keep a
committed snapshot of dataset size over time.
"""
from __future__ import annotations

import json
from collections import Counter

from .common import DATA_DIR, DISHES_DIR


def compute() -> dict:
    total = 0
    with_recipe = 0
    with_images = 0
    image_files = 0
    nationalities: Counter[str] = Counter()

    for path in DISHES_DIR.glob("*.json"):
        try:
            rec = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        total += 1
        if rec.get("recipe"):
            with_recipe += 1
        imgs = rec.get("images") or []
        if imgs:
            with_images += 1
        image_files += len(imgs)
        for nat in rec.get("nationality") or []:
            nationalities[nat] += 1

    complete = (DATA_DIR / ".complete").read_text(encoding="utf-8").strip() \
        if (DATA_DIR / ".complete").exists() else "unknown"

    return {
        "dishes": total,
        "with_recipe": with_recipe,
        "with_images": with_images,
        "image_files": image_files,
        "distinct_nationalities": len(nationalities),
        "top_nationalities": nationalities.most_common(15),
        "complete": complete,
    }


def to_markdown(s: dict) -> str:
    lines = [
        "## World Dishes — progress",
        "",
        f"- **Dishes:** {s['dishes']:,}",
        f"- **With real recipe:** {s['with_recipe']:,}",
        f"- **With images:** {s['with_images']:,}  "
        f"({s['image_files']:,} image files)",
        f"- **Distinct nationalities:** {s['distinct_nationalities']}",
        f"- **Crawl complete:** {s['complete']}",
        "",
        "| Nationality | Dishes |",
        "|---|---|",
    ]
    for name, count in s["top_nationalities"]:
        lines.append(f"| {name} | {count} |")
    return "\n".join(lines) + "\n"


def main() -> None:
    s = compute()
    (DATA_DIR / "stats.json").write_text(
        json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")
    print(to_markdown(s))


if __name__ == "__main__":
    main()
