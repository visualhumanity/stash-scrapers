import json
import os
import re
import sys
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/GalleryDlTwitter/ — go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

# gallery-dl writes one "<media filename>.json" next to every downloaded file
# (--write-metadata). Its sibling "<cdn key>.info.json" is a lossy duplicate and
# "info.json" describes an arbitrary tweet in the directory, so neither is used.
SIDECAR_SUFFIX = ".json"

# Profile pictures and banners are written as sidecars too, but they are not posts.
NON_POST_SUBCATEGORIES = {"avatar", "background"}

MAX_TITLE_LENGTH = 120
FALLBACK_TIME_ZONE = "America/Toronto"


def sidecar_path(media_path: str) -> str:
    return media_path + SIDECAR_SUFFIX


def load_sidecar(path: str):
    """Read a sidecar; returns None when it is missing, unreadable or not a JSON object."""
    try:
        with open(path, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log.warning(f"Could not read sidecar '{path}': {e}")
        return None

    if not isinstance(data, dict):
        log.warning(f"Sidecar '{path}' is not a JSON object")
        return None
    return data


def local_zone():
    """The container's own TZ, quietly falling back to America/Toronto."""
    name = os.environ.get("TZ")
    if name:
        try:
            return ZoneInfo(name)
        except (ZoneInfoNotFoundError, ValueError):
            log.debug(f"TZ '{name}' is not a known time zone; using {FALLBACK_TIME_ZONE}")
    else:
        log.debug(f"TZ is not set; using {FALLBACK_TIME_ZONE}")

    try:
        return ZoneInfo(FALLBACK_TIME_ZONE)
    except ZoneInfoNotFoundError:
        log.warning(f"No time zone data for {FALLBACK_TIME_ZONE} (is tzdata installed?); leaving the date out")
        return None


def parse_date(value, zone):
    """gallery-dl dates are UTC 'YYYY-MM-DD HH:MM:SS'; Stash wants the local 'YYYY-MM-DD'."""
    if not isinstance(value, str) or zone is None:
        return None
    try:
        utc = datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
    except ValueError:
        return None
    return utc.astimezone(zone).strftime("%Y-%m-%d")


def is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def media_suffix(meta: dict) -> str:
    """' [i]' when the tweet has several media items, so their titles stay distinct."""
    num, count = meta.get("num"), meta.get("count")
    if is_int(num) and is_int(count) and count > 1 and num >= 1:
        return f" [{num}]"
    return ""


def make_title(content, suffix: str = ""):
    """First line of the caption, shortened so the whole title (suffix included) fits the limit."""
    if not isinstance(content, str):
        return None
    line = next((l.strip() for l in content.splitlines() if l.strip()), "")
    if not line:
        return None

    limit = MAX_TITLE_LENGTH - len(suffix)
    if len(line) > limit:
        cut = line[: limit - 1]
        # Drop a half-cut trailing word; a single unbroken word is cut hard
        if not line[limit - 1].isspace():
            cut = re.sub(r"\s+\S*$", "", cut)
        line = cut.rstrip() + "…"
    return line + suffix


def poster_handle(meta: dict):
    """The tweet poster. `author` is an empty object in a few sidecars; `user` always names the folder."""
    for key in ("author", "user"):
        user = meta.get(key)
        if isinstance(user, dict) and isinstance(user.get("name"), str) and user["name"]:
            return user["name"]
    return None


def make_tags(hashtags):
    if not isinstance(hashtags, list):
        return []
    seen = {}
    for tag in hashtags:
        if isinstance(tag, str) and tag.strip():
            seen.setdefault(tag.strip().casefold(), {"name": tag.strip()})
    return list(seen.values())


def scrape_metadata(meta: dict, zone):
    """Map a gallery-dl Twitter sidecar onto the fields shared by Stash scenes and images."""
    scraped = {}

    content = meta.get("content")
    title = make_title(content, media_suffix(meta))
    if title:
        scraped["title"] = title

    if isinstance(content, str) and content.strip():
        scraped["details"] = content.strip()

    date = parse_date(meta.get("date"), zone)
    if date:
        scraped["date"] = date

    handle = poster_handle(meta)

    # tweet_id can exceed 2^53, so it is only ever handled as an int or a string
    tweet_id = meta.get("tweet_id")
    if is_int(tweet_id) and tweet_id > 0:
        scraped["code"] = str(tweet_id)
        scraped["urls"] = [f"https://twitter.com/{handle or 'i'}/status/{tweet_id}"]

    if handle:
        profile = f"https://twitter.com/{handle}"
        scraped["performers"] = [{"name": handle, "urls": [profile]}]
        scraped["studio"] = {"name": handle, "urls": [profile]}

    tags = make_tags(meta.get("hashtags"))
    if tags:
        scraped["tags"] = tags

    return scraped


def scrape_paths(paths):
    """Scrape from the first file that has a sidecar. Returns (scraped, sidecar_path)."""
    for media_path in paths:
        sidecar = sidecar_path(media_path)
        meta = load_sidecar(sidecar)
        if meta is None:
            log.debug(f"No usable sidecar at '{sidecar}'")
            continue

        subcategory = meta.get("subcategory")
        if subcategory in NON_POST_SUBCATEGORIES:
            log.debug(f"'{sidecar}' is a profile {subcategory}, not a post; skipping")
            return {}, sidecar

        return scrape_metadata(meta, local_zone()), sidecar

    return None, None


def get_image_paths(image_id: str):
    """
    imageByFragment input carries no file paths, so ask Stash's GraphQL API (this needs
    py_common/config.ini). Returns None when the lookup itself failed; py_common has
    already logged why.
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
    result = graphql.callGraphQL(query, {"id": image_id})
    if result is None:
        return None
    files = dig(result, "findImage", "visual_files") or []
    return [f["path"] for f in files if f.get("path")]


def run(kind: str, item_id: str, paths):
    scraped, sidecar = scrape_paths(paths)
    if scraped is None:
        log.debug(f"{kind.capitalize()} {item_id}: no sidecar found for {paths}")
        print(json.dumps({}))
        return

    if scraped:
        log.info(f"{kind.capitalize()} {item_id}: scraped {', '.join(scraped)} from '{sidecar}'")
    print(json.dumps(scraped))


def run_scene(fragment: dict):
    scene_id = fragment.get("id", "unknown")
    paths = [f["path"] for f in fragment.get("files") or [] if f.get("path")]

    if not paths:
        log.error(f"Scene {scene_id} has no files; cannot locate a gallery-dl sidecar")
        print("null")
        sys.exit(0)

    run("scene", scene_id, paths)


def run_image(fragment: dict):
    image_id = fragment.get("id")

    if not image_id:
        log.error("Image fragment has no id; cannot look up file path")
        print("null")
        sys.exit(0)

    paths = get_image_paths(image_id)
    if paths is None:
        print(json.dumps({}))
        return

    if not paths:
        log.warning(f"Image {image_id}: Stash returned no files")
        print(json.dumps({}))
        return

    run("image", image_id, paths)


if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in ("scene", "image"):
        print("Usage: GalleryDlTwitter.py <scene|image>", file=sys.stderr)
        sys.exit(1)

    operation = sys.argv[1]
    fragment = json.loads(sys.stdin.read())

    if operation == "scene":
        run_scene(fragment)
    else:
        run_image(fragment)
