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

# gallery-dl Reddit filenames: "<title> - <YYYY-MM-DD> - <performer> - <index>.<ext>"
FILENAME_RE = re.compile(
    r'^(?P<title>.*) - (?P<date>\d{4}-\d{2}-\d{2}) - (?P<performer>.*) - (?P<index>\d+)$'
)


def parse_filename(stem: str):
    """
    Extract (title, date, performer) from a "<title> - <date> - <performer> - <index>" stem.

    Greedy '.*' groups for title/performer let the regex find the *last* valid
    " - YYYY-MM-DD - " / " - <index>$" boundaries via backtracking, which is correct
    even if a post title itself contains a literal " - ".

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


def get_image_path(image_id: str):
    """Fetch an image's file path from Stash's own GraphQL API (imageByFragment stdin has no path)."""
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
    result = graphql.callGraphQL(query, {"id": image_id})
    files = dig(result, "findImage", "visual_files") or []
    return files[0]["path"] if files else None


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


def run_scene(fragment: dict):
    scene_id = fragment.get("id", "unknown")

    if not fragment.get("files"):
        log.error(f"Scene {scene_id} has no files; cannot extract metadata from filename")
        print("null")
        sys.exit(0)

    path = fragment["files"][0]["path"]
    if len(fragment["files"]) > 1:
        log.debug(f"Scene {scene_id} has multiple files; using first: {path}")

    scraped = scrape_path(path)
    if scraped:
        log.info(f"Scene {scene_id}: extracted {scraped} from '{path}'")
        print(json.dumps(scraped))
    else:
        log.info(f"Scene {scene_id}: filename did not match expected pattern: '{path}'")
        print(json.dumps({}))


def run_image(fragment: dict):
    image_id = fragment.get("id")

    if not image_id:
        log.error("Image fragment has no id; cannot look up file path")
        print("null")
        sys.exit(0)

    path = get_image_path(image_id)
    if not path:
        log.error(f"Image {image_id}: could not resolve a file path via GraphQL")
        print(json.dumps({}))
        return

    scraped = scrape_path(path)
    if scraped:
        log.info(f"Image {image_id}: extracted {scraped} from '{path}'")
        print(json.dumps(scraped))
    else:
        log.info(f"Image {image_id}: filename did not match expected pattern: '{path}'")
        print(json.dumps({}))


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
