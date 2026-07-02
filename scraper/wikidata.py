"""Fetch the world's dishes from Wikidata via SPARQL.

Wikidata item Q746549 = "dish" (a prepared food). We pull every instance of it
and its subclasses, with country of origin, cuisine, and a representative image.
This is the only free, legal source with structured region/nationality data at
scale (10k+ dishes).
"""
from __future__ import annotations

from .common import RateLimiter, get_json

SPARQL_URL = "https://query.wikidata.org/sparql"

# One page of results. We paginate with LIMIT/OFFSET to stay under the
# 60s query timeout of the public endpoint.
QUERY = """
SELECT ?dish ?dishLabel ?dishDescription
       (SAMPLE(?image) AS ?img)
       (GROUP_CONCAT(DISTINCT ?countryLabel; separator=" | ") AS ?countries)
       (GROUP_CONCAT(DISTINCT ?cuisineLabel; separator=" | ") AS ?cuisines)
WHERE {
  ?dish wdt:P279* wd:Q746549 .
  OPTIONAL { ?dish wdt:P18 ?image . }
  OPTIONAL { ?dish wdt:P495 ?country . ?country rdfs:label ?countryLabel .
             FILTER(LANG(?countryLabel) = "en") }
  OPTIONAL { ?dish wdt:P2012 ?cuisine . ?cuisine rdfs:label ?cuisineLabel .
             FILTER(LANG(?cuisineLabel) = "en") }
  ?dish rdfs:label ?dishLabel . FILTER(LANG(?dishLabel) = "en")
  OPTIONAL { ?dish schema:description ?dishDescription .
             FILTER(LANG(?dishDescription) = "en") }
}
GROUP BY ?dish ?dishLabel ?dishDescription
ORDER BY ?dish
LIMIT %d OFFSET %d
"""

PAGE_SIZE = 500


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def iter_dishes(session):
    """Yield dish dicts from Wikidata, paginated."""
    limiter = RateLimiter(2.0)  # be gentle to the public endpoint
    offset = 0
    while True:
        query = QUERY % (PAGE_SIZE, offset)
        data = get_json(
            session, SPARQL_URL,
            params={"query": query, "format": "json"},
            limiter=limiter,
        )
        if not data:
            print("  ! Wikidata page failed; stopping pagination.")
            return
        rows = data.get("results", {}).get("bindings", [])
        if not rows:
            return
        for row in rows:
            def val(key):
                return row.get(key, {}).get("value", "") or ""

            countries = [c for c in val("countries").split(" | ") if c]
            cuisines = [c for c in val("cuisines").split(" | ") if c]
            yield {
                "wikidata_id": _qid(val("dish")),
                "name": val("dishLabel"),
                "description": val("dishDescription"),
                "countries": countries,          # nationality / country of origin
                "cuisines": cuisines,            # region / cuisine
                "wikidata_image": val("img"),    # Commons full URL (P18)
            }
        offset += PAGE_SIZE
        print(f"  .. Wikidata: fetched {offset} dishes so far")
