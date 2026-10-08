import glob
import html
import json
import os
import re
import sqlite3
import sys
import tempfile
from datetime import datetime, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

SCRAPERS_DIR = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, os.path.join(SCRAPERS_DIR, "community"))
sys.path.insert(0, os.path.join(SCRAPERS_DIR, "ConvertHtmlToMarkdown"))

try:
    from py_common import log
except ModuleNotFoundError:
    print(
        "You need to download the folder 'py_common' from the community repo! "
        "(CommunityScrapers/tree/master/scrapers/py_common)",
        file=sys.stderr,
    )
    sys.exit(1)

try:
    from ConvertHtmlToMarkdown import html_to_markdown, looks_like_html
except ModuleNotFoundError:
    html_to_markdown = looks_like_html = None
    log.warning("ConvertHtmlToMarkdown scraper not found; descriptions stay HTML")

MODEL_FOLDER = re.compile(r"^(?P<name>.*) \((?P<username>[^()]+)\)$")
CACHE_FILE = os.path.join(os.path.dirname(os.path.realpath(__file__)), "cache_db_location.json")

TITLE_MIN = 30
TITLE_MAX = 90
TRIM = " ,;:-–"
SENTENCE_PUNCTUATION = ".!?…。！？"
ABBREVIATIONS = {"pt", "min", "vs", "ft", "no", "dr", "mr", "mrs", "st"}
ACRONYMS = {"POV", "PT", "HD", "VR", "DM", "BJ", "DP", "XXX", "GFE", "JOI", "ASMR", "BBC", "FTM"}
SMALL_WORDS = {"a", "an", "the", "and", "or", "of", "in", "on", "at", "to", "for", "with", "vs"}

EMOJI = (
    "‼⁉↔-↪⌚-⏿▪-◾☀-➿⤴⤵⬅-⭕"
    "〰〽㊗㊙\U0001f000-\U0001faff"
)
EMOJI_UNIT = f"[{EMOJI}][{EMOJI}️‍⃣]*"
EMOJI_RUN = rf"{EMOJI_UNIT}(?:\s+{EMOJI_UNIT})*"
EMOJI_UNIT_RE = re.compile(EMOJI_UNIT)
EMOJI_AFTER = re.compile(rf"\s*{EMOJI_RUN}")
SEGMENT_END = re.compile(rf"{EMOJI_RUN}|[.!?]+(?=\s|$|[{EMOJI}])|[…。！？]+")

FILLER = re.compile("|".join([
    r"\b(?:the )?links? (?:in (?:my )?(?:bio|comments?)|below|above)\b",
    r"\bcheck (?:out )?the link\b",
    r"\btips? (?:menu|welcome)\b",
    r"\btip\s*\$?\d[^.!?…。！？]*",
    r"\bthank(?:s| you)(?: so much)? for (?:subscribing|the support|watching)\b",
    r"\b(?:subscribe|sub) now\b",
    r"\bdm me\b",
    r"\bmessage me\b",
    r"\bcheck your dms\b",
    r"\bunlock now\b",
    r"\bstream started at[^.!?…。！？]*",
]), re.I)
PREFIX = re.compile(r"^\s*(?:free\s*[:\-–]\s*|\d+\s*(?:min(?:ute)?s?)\.?\s*(?:[:\-–]|of\b)\s*)+", re.I)

QUERY = """
SELECT m.post_id,
       COALESCE(p.created_at, ms.created_at, s.created_at),
       COALESCE(p.text, ms.text, s.text),
       p.post_id IS NOT NULL
FROM medias m
LEFT JOIN posts p ON m.api_type IN ('Timeline','Archived','Pinned','Paid') AND p.post_id = m.post_id
LEFT JOIN messages ms ON m.api_type IN ('Message','Messages') AND ms.post_id = m.post_id
LEFT JOIN stories s ON m.api_type IN ('Highlights','Stories') AND s.post_id = m.post_id
WHERE m.media_id = ?
"""


def local_zone():
    return ZoneInfo(os.environ.get("TZ") or "America/Toronto")


def to_local_date(created_at):
    moment = datetime.fromisoformat(created_at)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(local_zone()).strftime("%Y-%m-%d")


def split_path(path):
    """Return (download_root, model_folder, display_name, username) for <root>/<model>/<type>/<media>/<file>."""
    parts = os.path.normpath(path).split(os.sep)
    if len(parts) < 5 or not parts[-4]:
        return None
    root = os.sep.join(parts[:-4]) or os.sep
    folder = parts[-4]
    match = MODEL_FOLDER.match(folder)
    if match:
        return root, folder, match["name"], match["username"]
    return root, folder, folder, folder


def media_id_from(filename):
    match = re.search(r"_(\d+)\]\.[^.]+$", filename)
    return int(match[1]) if match else None


def db_paths(root):
    return sorted(glob.glob(os.path.join(glob.escape(root), ".data", "*", "user_data.db")))


def lookup(db_path, media_id):
    uri = "file:" + quote(db_path) + "?mode=ro"
    try:
        con = sqlite3.connect(uri, uri=True)
        try:
            return con.execute(QUERY, (media_id,)).fetchone()
        finally:
            con.close()
    except sqlite3.Error as exc:
        log.warning(f"Could not read {db_path}: {exc}")
        return None


def read_cache():
    try:
        with open(CACHE_FILE) as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def write_cache(cache):
    try:
        fd, tmp = tempfile.mkstemp(dir=os.path.dirname(CACHE_FILE), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            json.dump(cache, f, indent=2)
        os.replace(tmp, CACHE_FILE)
    except OSError as exc:
        log.warning(f"Could not write cache: {exc}")


def find_row(root, folder, username, media_id):
    cache = read_cache()
    cached = cache.get(folder)
    if cached is not None and not os.path.isfile(cached):
        del cache[folder]
        write_cache(cache)
        cached = None
    if cached:
        row = lookup(cached, media_id)
        if row:
            return row

    derived = [p for p in db_paths(root) if os.path.basename(os.path.dirname(p)).startswith(username + "_")]
    for path in derived:
        row = lookup(path, media_id)
        if row:
            return row

    for path in db_paths(root):
        if path in derived or path == cached:
            continue
        row = lookup(path, media_id)
        if row:
            cache[folder] = path
            write_cache(cache)
            return row
    return None


def add_unique(names, seen, candidate):
    candidate = candidate.rstrip(".-")
    key = candidate.lower()
    if candidate and key not in seen:
        seen.add(key)
        names.append(candidate)


def mentions(text, own_username):
    seen = {own_username.lower(), "my"}
    names = []
    link = re.compile(r"""(?:href=["']/|onlyfans\.com/)([\w.\-]+)(?![\w.\-]|/\w)""")
    for found in link.findall(text):
        if not found.isdigit():
            add_unique(names, seen, found)
    plain = re.sub(r"<[^>]*>", " ", text)
    for found in re.findall(r"(?<!\w)@([\w.\-]+)", plain):
        add_unique(names, seen, found)
    return names


def to_markdown(text):
    if html_to_markdown is None or not looks_like_html(text):
        return text
    absolute = re.sub(r"""(href=["'])/(?!/)""", r"\1https://onlyfans.com/", text)
    return html_to_markdown(absolute) or text


def plain_lines(text):
    text = re.sub(r"(?i)</p>\s*<p[^>]*>|<br\s*/?>|</?p[^>]*>", "\n", text)
    text = re.sub(r"</?[A-Za-z][^>]*>", "", text)
    text = html.unescape(text).replace("\xa0", " ")
    text = text.replace("**", "").replace("__", "")
    return [line.strip() for line in text.splitlines() if line.strip()]


def segments(line):
    parts, start, pos = [], 0, 0
    while True:
        found = SEGMENT_END.search(line, pos)
        if not found:
            break
        end = found.end()
        if found.group() == ".":
            word = re.search(r"(\w+)$", line[:found.start()])
            if word and word.group(1).lower() in ABBREVIATIONS:
                pos = end
                continue
        if found.group()[0] in SENTENCE_PUNCTUATION:
            trailing = EMOJI_AFTER.match(line, end)
            if trailing:
                end = trailing.end()
        parts.append(line[start:end])
        start = pos = end
    parts.append(line[start:])
    cleaned = []
    for part in parts:
        part = re.sub(r"\s+", " ", FILLER.sub("", part)).strip(TRIM)
        if any(c.isalnum() for c in part) or EMOJI_UNIT_RE.search(part):
            cleaned.append(part)
    return cleaned


def title_case(title):
    body = re.sub(r"@[\w.\-]+", "", title)
    if not any(c.isalpha() for c in body) or any(c.islower() for c in body):
        return title
    first = [True]

    def fix(found):
        word = found.group()
        is_first, first[0] = first[0], False
        if word.startswith("@") or word in ACRONYMS:
            return word
        low = word.lower()
        return low if low in SMALL_WORDS and not is_first else low.capitalize()

    return re.sub(r"@[\w.\-]+|[A-Za-z][A-Za-z’']*", fix, title)


def finish_title(title):
    title = re.sub(r"\s+", " ", title).strip(TRIM)
    title = re.sub(r"(?<!\.)\.$|。$", "", title)
    title = title_case(title)
    if len(title) > TITLE_MAX:
        head = title[:TITLE_MAX - 1]
        if not title[TITLE_MAX - 1].isspace() and " " in head:
            head = head.rsplit(" ", 1)[0]
        title = head.rstrip(TRIM + ".‍") + "…"
    return title


def infer_title(text):
    for line in plain_lines(text or ""):
        line = re.sub(r"(?:https?://|www\.)\S+", "", line)
        line = PREFIX.sub("", line)
        parts = segments(line)
        if not any(c.isalnum() for c in "".join(parts)):
            continue
        title = ""
        for part in parts:
            title = f"{title} {part}".strip()
            if len(title) >= TITLE_MIN:
                break
        return finish_title(title) or None
    return None


def scrape(fragment):
    files = fragment.get("files") or []
    if not files:
        return {}
    path = files[0]["path"]
    located = split_path(path)
    media_id = media_id_from(os.path.basename(path))
    if not located or media_id is None:
        return {}
    root, folder, name, username = located
    row = find_row(root, folder, username, media_id)
    if not row:
        return {}
    post_id, created_at, text, is_post = row
    performers = [name]
    seen = {name.lower()}
    for mention in mentions(text or "", username):
        add_unique(performers, seen, mention)
    result = {
        "studio": {"name": username},
        "performers": [{"name": n} for n in performers],
    }
    if created_at:
        result["date"] = to_local_date(created_at)
    if is_post:
        result["urls"] = [f"https://onlyfans.com/{post_id}/{username}"]
    title = infer_title(text)
    if title:
        result["title"] = title
    if text:
        result["details"] = to_markdown(text)
    return result


if __name__ == "__main__":
    try:
        print(json.dumps(scrape(json.load(sys.stdin))))
    except Exception as exc:
        log.error(f"OF-Scraper - User Data failed: {exc}")
        print("null")
