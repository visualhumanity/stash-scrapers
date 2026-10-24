import glob
import json
import os
import re
import sys
from datetime import datetime, timezone

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/GalleryDlReddit/ — go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

# gallery-dl writes "<media file name>.json" next to each file (--write-metadata).
# Only that file is read; "<media id>.info.json" files and a folder's "info.json"
# are never opened.
METADATA_SUFFIX = ".json"

REDDIT = "https://www.reddit.com"

# Reddit's placeholder author for deleted accounts
DELETED_AUTHOR = "[deleted]"

# Folder gallery-dl Reddit downloads are filed under, e.g. ".../r_ExampleSub/<file>"
SUBREDDIT_FOLDER_RE = re.compile(r"^r_(?P<subreddit>.+)$")

# Longest text value written into one log line. Stash 0.31.1 reads scraper stderr with a
# 64 KiB line limit and closes the pipe on a longer line, which kills the scraper before
# it prints its result; post text alone can be 160 KB in UTF-8.
LOG_VALUE_LIMIT = 80

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


def short(value) -> str:
    """A value for a log line: text cut to LOG_VALUE_LIMIT characters, with its full length."""
    text_value = str(value)
    if len(text_value) <= LOG_VALUE_LIMIT:
        return text_value
    return f"{text_value[:LOG_VALUE_LIMIT]}... ({len(text_value)} chars)"


def describe(scraped: dict) -> str:
    """Field names, with short text values quoted, for the success log line."""
    return ", ".join(
        f"{key} {short(value)!r}" if isinstance(value, str) else key for key, value in scraped.items()
    )


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
        log.error(f"Image {image_id}: GraphQL lookup failed: {short(e)}")
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


def load_metadata(media_path: str):
    """
    Read the gallery-dl metadata file next to a media file. Returns None when it is
    missing, unreadable, not a JSON object, or not Reddit data (e.g. RedGIFs).
    """
    path = media_path + METADATA_SUFFIX
    try:
        with open(path, encoding="utf-8") as f:
            meta = json.load(f)
    except FileNotFoundError:
        return None
    except (OSError, ValueError) as e:
        log.warning(f"Could not read metadata file '{path}': {short(e)}")
        return None

    if not isinstance(meta, dict):
        log.warning(f"Metadata file '{path}' is not a JSON object")
        return None
    if meta.get("category") != "reddit":
        log.debug(f"Metadata file '{path}' holds {short(meta.get('category'))!r} data, not Reddit; using the file name")
        return None
    return meta


def text(value):
    """A trimmed non-empty string, else None."""
    if isinstance(value, str) and value.strip():
        return value.strip()
    return None


def post_date(meta: dict):
    """
    The post's UTC date. gallery-dl's `date` is created_utc as UTC "YYYY-MM-DD HH:MM:SS",
    the same date its file names carry, so no time zone conversion is done.
    """
    value = meta.get("date")
    if isinstance(value, str):
        try:
            return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d")
        except ValueError:
            pass

    created = meta.get("created_utc")
    if isinstance(created, (int, float)) and not isinstance(created, bool):
        try:
            return datetime.fromtimestamp(created, timezone.utc).strftime("%Y-%m-%d")
        except (OverflowError, OSError, ValueError):
            pass
    return None


def make_performer(author: str):
    return {"name": f"u_{author}", "urls": [f"{REDDIT}/user/{author}"]}


def make_studio(subreddit: str):
    return {"name": f"r/{subreddit}", "urls": [f"{REDDIT}/r/{subreddit}"], "parent": {"name": "Reddit"}}


def scrape_metadata(meta: dict):
    """Map a gallery-dl Reddit metadata file onto the fields shared by scenes and images."""
    scraped = {}

    title = text(meta.get("title"))
    if title:
        scraped["title"] = title

    date = post_date(meta)
    if date:
        scraped["date"] = date

    permalink = text(meta.get("permalink"))
    if permalink and permalink.startswith("/"):
        scraped["urls"] = [REDDIT + permalink]

    post_id = text(meta.get("id"))
    if post_id:
        scraped["code"] = post_id

    details = text(meta.get("selftext"))
    if details:
        scraped["details"] = details

    author = text(meta.get("author"))
    if author and author != DELETED_AUTHOR:
        scraped["performers"] = [make_performer(author)]

    subreddit = text(meta.get("subreddit"))
    if subreddit:
        scraped["studio"] = make_studio(subreddit)

    flair = text(meta.get("link_flair_text"))
    if flair:
        scraped["tags"] = [{"name": flair}]

    return scraped


def filename_performer(name: str):
    """A "u_<author>" name gets the same profile URL as the metadata path; other names get none."""
    if name.startswith("u_") and len(name) > 2:
        return make_performer(name[2:])
    return {"name": name}


def scrape_filename(path: str):
    """Fallback: title, date and performer from the file name, studio from an r_<subreddit> folder."""
    filename = os.path.splitext(os.path.basename(path))[0]
    parsed = parse_filename(filename)
    if not parsed:
        return None
    title, date, performer = parsed
    scraped = {
        "title": title,
        "date": date,
    }
    if performer != f"u_{DELETED_AUTHOR}":
        scraped["performers"] = [filename_performer(performer)]

    folder = SUBREDDIT_FOLDER_RE.match(os.path.basename(os.path.dirname(path)))
    if folder:
        scraped["studio"] = make_studio(folder.group("subreddit"))
    return scraped


def file_number(path: str):
    """The gallery number from a file name's " - <n>" suffix, or None."""
    m = FILENAME_RE.match(os.path.splitext(os.path.basename(path))[0])
    if m and m.group("index"):
        return int(m.group("index"))
    return None


def first_image_paths(path: str):
    """
    Candidate media paths for image 1 of the same gallery post: the same file name with
    " - 1" in the same folder. The same extension is tried first; image 1 can have
    another one (a .png in a gallery of .jpg files).
    """
    folder, name = os.path.split(path)
    stem, ext = os.path.splitext(name)
    m = FILENAME_RE.match(stem)
    first_stem = stem[: m.start("index")] + "1"

    candidates = [os.path.join(folder, first_stem + ext)]
    pattern = os.path.join(glob.escape(folder), glob.escape(first_stem) + ".*" + METADATA_SUFFIX)
    for metadata_path in sorted(glob.glob(pattern)):
        media = metadata_path[: -len(METADATA_SUFFIX)]
        if media not in candidates and not media.endswith(".info"):
            candidates.append(media)
    return candidates


def find_metadata(path: str, number):
    """
    The usable metadata for a media file, and the metadata file it came from. Images 2 to N
    of a gallery post have no metadata file of their own, so they use image 1's.
    """
    meta = load_metadata(path)
    if meta is not None:
        return meta, path + METADATA_SUFFIX

    if number is None or number < 2 or os.path.exists(path + METADATA_SUFFIX):
        return None, None

    for first in first_image_paths(path):
        meta = load_metadata(first)
        if meta is not None:
            return meta, first + METADATA_SUFFIX
    return None, None


def gallery_size(meta: dict):
    """The number of items in a gallery post, or None when the metadata does not say."""
    gallery = meta.get("gallery_data")
    if isinstance(gallery, dict) and isinstance(gallery.get("items"), list) and gallery["items"]:
        return len(gallery["items"])
    return None


def number_title(scraped: dict, number, total):
    """
    Add " [n/N]" to the title of an image in a post with more than one image, or " [n]"
    when the total is unknown. Numbers below 1 (" - 0", single-image posts), a missing
    suffix and one-item galleries leave the title as it is.
    """
    if "title" not in scraped or number is None or number < 1:
        return
    if total is None:
        scraped["title"] += f" [{number}]"
    elif total > 1:
        scraped["title"] += f" [{number}/{total}]"


def scrape_metadata_path(path: str):
    """Returns (scraped, source) from a file's metadata file (its own or image 1's), or (None, None)."""
    number = file_number(path)
    meta, metadata_path = find_metadata(path, number)
    if meta is None:
        return None, None

    scraped = scrape_metadata(meta)
    if not scraped:
        log.debug(f"Metadata file '{metadata_path}' has no usable fields")
        return None, None
    number_title(scraped, number, gallery_size(meta))
    return scraped, f"metadata file '{metadata_path}'"


def scrape_filename_path(path: str):
    """Returns (scraped, source) from a file's name, or (None, None)."""
    scraped = scrape_filename(path)
    if not scraped:
        return None, None
    number_title(scraped, file_number(path), None)
    return scraped, f"file name '{path}'"


def run(kind: str, item_id: str, paths):
    """
    Metadata files of all paths are tried before any file name, so an old-format
    duplicate without a metadata file never beats a file that has one.
    """
    for scrape in (scrape_metadata_path, scrape_filename_path):
        for path in paths:
            scraped, source = scrape(path)
            if scraped:
                log.info(f"{kind} {item_id}: extracted {describe(scraped)} from {source}")
                print(json.dumps(scraped))
                return

    log.info(f"{kind} {item_id}: no Reddit metadata file and no file name matching the expected pattern: {paths}")
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
