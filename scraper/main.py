"""Orchestrate: Wikidata dishes -> TheMealDB recipes -> images -> JSON.

Resumable: processed Wikidata IDs are recorded in data/state.json so a run can
be stopped (e.g. GitHub Actions time limit) and continued without redoing work.

Usage:
    python -m scraper.main --max 300     # process up to 300 new dishes
    python -m scraper.main               # process everything remaining
"""
from __future__ import annotations

import argparse
import json
import time

from .common import DISHES_DIR, STATE_FILE, make_session, slugify
from .images import download_images
from .mealdb import fetch_recipe
from .wikidata import iter_dishes


def load_state() -> set[str]:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")).get("done", []))
    return set()


def save_state(done: set[str]) -> None:
    STATE_FILE.write_text(
        json.dumps({"done": sorted(done)}, indent=0), encoding="utf-8"
    )


def build_record(session, dish: dict) -> dict:
    recipe = fetch_recipe(session, dish["name"])
    slug = slugify(dish["name"]) + "-" + dish["wikidata_id"].lower()

    images = download_images(
        slug, dish["name"], dish.get("wikidata_image", ""),
        recipe.get("thumb", "") if recipe else "",
    )

    # Nationality: prefer Wikidata country of origin, fall back to MealDB area.
    nationality = dish["countries"] or ([recipe["area"]] if recipe and recipe.get("area") else [])

    return {
        "id": dish["wikidata_id"],
        "name": dish["name"],
        "description": dish["description"],
        "nationality": nationality,
        "region_cuisine": dish["cuisines"] or ([recipe["category"]] if recipe and recipe.get("category") else []),
        "images": images,
        "recipe": recipe,          # None when no free recipe was found
        "sources": {
            "wikidata": f"https://www.wikidata.org/wiki/{dish['wikidata_id']}",
            "themealdb": recipe["source_id"] if recipe else None,
        },
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max", type=int, default=0,
                    help="max new dishes to process this run (0 = no limit)")
    ap.add_argument("--time-budget", type=int, default=0,
                    help="stop cleanly after N seconds (0 = no limit). "
                         "Set below the 6h Actions cap to avoid hard kills.")
    args = ap.parse_args()

    session = make_session()
    done = load_state()
    processed = 0
    start = time.time()
    complete = True  # becomes False if we stop early with work remaining

    print(f"Starting. {len(done)} dishes already done.")
    for dish in iter_dishes(session):
        if not dish["name"] or dish["wikidata_id"] in done:
            continue

        record = build_record(session, dish)
        out = DISHES_DIR / f"{record['id']}.json"
        out.write_text(json.dumps(record, indent=2, ensure_ascii=False),
                       encoding="utf-8")

        done.add(dish["wikidata_id"])
        processed += 1
        print(f"[{processed}] {record['name']} "
              f"({len(record['images'])} imgs, "
              f"recipe={'yes' if record['recipe'] else 'no'})")

        # Checkpoint often so a hard kill loses at most a few dishes.
        if processed % 25 == 0:
            save_state(done)

        if args.max and processed >= args.max:
            print("Reached --max for this run.")
            complete = False
            break
        if args.time_budget and (time.time() - start) >= args.time_budget:
            print("Reached --time-budget for this run.")
            complete = False
            break

    save_state(done)
    # Signal to the workflow whether more work remains, so it can re-trigger.
    (STATE_FILE.parent / ".complete").write_text(
        "yes" if complete else "no", encoding="utf-8")
    print(f"Done. Processed {processed} new dishes in "
          f"{time.time() - start:.0f}s. Total: {len(done)}. "
          f"Complete: {complete}.")


if __name__ == "__main__":
    main()
