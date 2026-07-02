# World Dishes Scraper

![Scrape world dishes](../../actions/workflows/scrape.yml/badge.svg)

> **Live progress:** see [`data/stats.json`](data/stats.json) (dish count,
> recipes, images, nationalities) — refreshed and committed after every run,
> and shown in each Actions run's summary.

Builds a free, legally-safe dataset of dishes from around the world — with
**region / nationality**, **description**, **real recipes** (where a free source
has them), and **up to 4 openly-licensed images** each — and commits it as JSON
into this repo. Designed to run on **GitHub Actions' free public tier**.

## Sources (all free)

| Source | Provides | Coverage |
|---|---|---|
| **Wikidata** (SPARQL) | dish, country of origin, cuisine, image | 10,000+ dishes |
| **TheMealDB** API | ingredients + full instructions | ~300 dishes |
| **Wikimedia Commons** | openly-licensed images (≤4/dish) | huge |

> Full cooking instructions only exist for dishes TheMealDB covers. Scraping
> copyrighted recipe sites (AllRecipes, NYT Cooking, etc.) is deliberately
> avoided — it violates their terms and risks getting the repo/Actions banned.

## Output layout

```
data/
  dishes/<wikidata-id>.json   # one file per dish
  images/<slug>/*.jpg          # up to 4 images per dish
  state.json                   # checkpoint of processed dishes (resumable)
```

Each dish JSON:

```json
{
  "id": "Q207965",
  "name": "Sushi",
  "description": "Japanese dish of vinegared rice",
  "nationality": ["Japan"],
  "region_cuisine": ["Japanese cuisine"],
  "images": ["images/sushi-q207965/sushi-q207965-1.jpg"],
  "recipe": { "source": "TheMealDB", "ingredients": [...], "instructions": "..." },
  "sources": { "wikidata": "...", "themealdb": "..." }
}
```

## Run locally

```bash
pip install -r requirements.txt
python -m scraper.main --max 50     # small test run
python -m scraper.main              # process everything remaining
```

## Run on GitHub Actions

1. Push this repo (must be **public** for unlimited free minutes).
2. In **Settings → Actions → General**, set *Workflow permissions* to
   **Read and write**.
3. Trigger **Scrape world dishes** from the Actions tab (or wait for the daily
   cron). Each run processes a batch, commits results, and resumes next time via
   `data/state.json`.

## Politeness / etiquette

Requests are rate-limited and retried with backoff, and send a descriptive
User-Agent (required by Wikimedia). Adjust intervals in `scraper/common.py`.
