import json
import os
import sys

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/vhTitleFromPerformers/, so go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

# rating100 at or above this (3 of 5 stars) ranks ahead of unrated performers; below it ranks after
RATING_CUTOFF = 60

# Performers of these genders are listed after everyone else (male or no gender set)
LAST_GENDERS = frozenset({"FEMALE", "TRANSGENDER_MALE", "TRANSGENDER_FEMALE", "INTERSEX", "NON_BINARY"})

SCENE_PERFORMERS_QUERY = """
query FindScenePerformers($id: ID!) {
    findScene(id: $id) {
        performers { name gender rating100 }
    }
}
"""


def fetch_performers(scene_id: str):
    """
    The fragment carries no performer ratings, so ask Stash's GraphQL API for the saved
    scene (this needs the URL, and the API key when auth is on, in py_common/config.ini).
    Returns None when the lookup failed.
    """
    try:
        from py_common import graphql

        result = graphql.callGraphQL(SCENE_PERFORMERS_QUERY, {"id": scene_id})
    except Exception as e:
        log.error(f"Scene {scene_id}: Stash API request failed: {e}")
        return None
    if result is None:
        # py_common has already logged why
        log.error(f"Scene {scene_id}: Stash API request failed")
        return None
    scene = result.get("findScene")
    if scene is None:
        log.error(f"Scene {scene_id}: not found in Stash")
        return None
    return scene["performers"]


def rating_tier(rating) -> int:
    if rating is None:
        return 1
    return 0 if rating >= RATING_CUTOFF else 2


def sort_key(performer: dict):
    rating = performer.get("rating100")
    name = performer["name"]
    return (
        performer.get("gender") in LAST_GENDERS,
        rating_tier(rating),
        -(rating or 0),
        name.casefold(),
        # Names that differ only in case still get one fixed order
        name,
    )


def format_title(names: list[str]) -> str:
    if len(names) == 2:
        return " & ".join(names)
    return ", ".join(names[:-1]) + ", & " + names[-1]


def scrape(fragment):
    """Returns the fields to update, {} for none, or None on a fatal error."""
    scene_id = fragment.get("id") if isinstance(fragment, dict) else None
    if not scene_id:
        log.error(f"Fragment has no scene id: {fragment!r}")
        return None
    performers = fetch_performers(scene_id)
    if performers is None:
        return None
    if len(performers) < 2:
        log.info(f"Scene {scene_id}: {len(performers)} performer(s), no title suggested")
        return {}
    return {"title": format_title([p["name"] for p in sorted(performers, key=sort_key)])}


if __name__ == "__main__":
    try:
        fragment = json.loads(sys.stdin.read())
    except ValueError as e:
        log.error(f"Invalid JSON on stdin: {e}")
        print("null")
        sys.exit(0)
    print(json.dumps(scrape(fragment)))
