import json
import os
import re
import sys
from datetime import datetime

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/GalleryDlReddit/ — go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

# gallery-dl Reddit filenames: "<title> - <YYYY-MM-DD> - <performer>[ - <index>].<ext>"
# The trailing " - <index>" is only present on multi-file posts (galleries); single-file
# posts (e.g. a lone video) omit it, so it must be optional.
FILENAME_RE = re.compile(
    r'^(?P<title>.*) - (?P<date>\d{4}-\d{2}-\d{2}) - (?P<performer>.*?)(?: - (?P<index>\d+))?$'
)


def parse_filename(stem: str):
    """
    Extract (title, date, performer) from a "<title> - <date> - <performer>[ - <index>]" stem.

    Greedy '.*' for title lets the regex find the *last* valid " - YYYY-MM-DD - " boundary
    via backtracking, correct even if a post title itself contains a literal " - ". Performer
    is non-greedy so it only yields characters to the optional trailing index group when that
    group can actually match (i.e. there's a literal " - <digits>" at the very end) — a
    performer name that itself ends in digits (e.g. "u_Example_User_1234") is left intact.

    Returns None if the pattern doesn't match or the date isn't a valid calendar date.
    """
    m = FILENAME_RE.match(stem)
    if not m:
        return None

    try:
        date = datetime.strptime(m.group("date"), "%Y-%m-%d").strftime("%Y-%m-%d")
    except ValueError:
        return None

    return m.group("title").strip(), date, m.group("performer").strip()


def get_image_paths(image_id: str):
    """
    Ask Stash's GraphQL API for an image's file paths (older Stash builds send no paths
    in the imageByFragment input). Returns None when the lookup itself failed.
    """
    from py_common import graphql
    from py_common.util import dig

    query = """
    query FindImage($id: ID!) {
        findImage(id: $id) {
            visual_files {
                ... on BaseFile { path }
            }
        }
    }
    """
    try:
        result = graphql.callGraphQL(query, {"id": image_id})
    except Exception as e:
        log.error(f"Image {image_id}: GraphQL lookup failed: {e}")
        return None
    if result is None:
        # py_common has already logged the reason (no URL, bad API key, ...)
        log.error(f"Image {image_id}: GraphQL lookup failed; check py_common/config.ini")
        return None
    files = dig(result, "findImage", "visual_files") or []
    return [f["path"] for f in files if isinstance(f, dict) and f.get("path")]


def input_paths(fragment: dict):
    """File paths from the scrape input (scenes, and images on newer Stash builds)."""
    return [f["path"] for f in fragment.get("files") or [] if isinstance(f, dict) and f.get("path")]


def scrape_path(path: str):
    filename = os.path.splitext(os.path.basename(path))[0]
    parsed = parse_filename(filename)
    if not parsed:
        return None
    title, date, performer = parsed
    return {
        "title": title,
        "date": date,
        "performers": [{"name": performer}],
    }


def run(kind: str, item_id: str, paths):
    """Scrape from the first path that yields a result."""
    for path in paths:
        scraped = scrape_path(path)
        if scraped:
            log.info(f"{kind} {item_id}: extracted {scraped} from '{path}'")
            print(json.dumps(scraped))
            return

    log.info(f"{kind} {item_id}: no filename matched the expected pattern: {paths}")
    print(json.dumps({}))


def run_scene(fragment: dict):
    scene_id = fragment.get("id", "unknown")
    paths = input_paths(fragment)

    if not paths:
        log.error(f"Scene {scene_id} has no files; cannot extract metadata from filename")
        print("null")
        sys.exit(0)

    run("Scene", scene_id, paths)


def run_image(fragment: dict):
    image_id = fragment.get("id")

    if not image_id:
        log.error("Image fragment has no id; cannot look up file path")
        print("null")
        sys.exit(0)

    paths = input_paths(fragment)
    if not paths:
        paths = get_image_paths(image_id)
        if paths is None:
            print(json.dumps({}))
            return
        if not paths:
            log.warning(f"Image {image_id}: Stash returned no files for this image")
            print(json.dumps({}))
            return

    run("Image", image_id, paths)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("scene", "image"):
        print("Usage: GalleryDlReddit.py <scene|image>", file=sys.stderr)
        sys.exit(1)

    operation = sys.argv[1]
    fragment = json.loads(sys.stdin.read())

    if operation == "scene":
        run_scene(fragment)
    else:
        run_image(fragment)
