import json
import os
import re
import sys
import unicodedata
from datetime import datetime, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/DateFromFilename/ — go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

YEAR_MIN = 1900
YEAR_MAX = 2100
FALLBACK_TIME_ZONE = "America/Toronto"
# 2000-01-01 00:00 UTC: the earliest Unix timestamp accepted
TIMESTAMP_MIN = 946684800


def is_valid_year(y: int) -> bool:
    return YEAR_MIN <= y <= YEAR_MAX


def try_date(year: int, month: int, day: int):
    """Return YYYY-MM-DD string if the combination is a valid calendar date, else None."""
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


DAY, MONTH, YEAR = 0, 1, 2

class Language:
    """Month words, ordinal suffixes and connector words of one language."""

    def __init__(self, full, abbreviated, ordinal, day_connector=None, year_connector=None,
                 ordinal_on_first_only=False):
        self.months = {**full, **abbreviated}
        self.ordinal_on_first_only = ordinal_on_first_only
        # Abbreviations may end in a period ("Feb."); full names may not
        letter = r"[^\W\d_]"
        # Abbreviations may end in a period ("Feb."); full names may not.
        # A month word must not touch other letters ("Marvel", "Decent").
        plain = rf"(?<!{letter})(?P<mon>{alternation(full)}|{alternation(abbreviated)})(?!{letter})"
        mon = (
            rf"(?<!{letter})(?P<mon>{alternation(full)}|(?:{alternation(abbreviated)})\.?)"
            rf"(?!{letter})"
        )
        sep = r"(?P<sep>[ ._-])"
        # The day may take an ordinal suffix and a comma ("Feb 16th, 2025")
        day = rf"(?<!\d)(?P<day>\d{{1,2}})(?!\d)(?P<ord>{ordinal})?"
        year4 = r"(?<!\d)(?P<year>\d{4})(?!\d)"
        # A two-digit year must not run into letters or digits ("25min")
        short = r"\d{2}(?![^\W_])"
        # With a day present, a two-digit year needs no apostrophe ("16 Feb 25")
        year = rf"(?<!\d)(?P<year>\d{{4}}(?!\d)|'?{short})"
        # Without a day, it does ("Feb '25"); "Feb 25" could be a day
        month_year = rf"(?<!\d)(?P<year>\d{{4}}(?!\d)|'{short})"
        day_connector = rf"(?:{day_connector}(?P=sep))?" if day_connector else ""
        year_connector = rf"(?:{year_connector}(?P=sep))?" if year_connector else ""
        self.formats = [
            # Month first: Feb 16 2025
            (DAY, rf"{mon}{sep}{day},?(?P=sep){year}"),
            # Day first: 16 Feb 2025, 16th of February 2025
            (DAY, rf"{day},?{sep}{day_connector}{mon}(?P=sep){year_connector}{year}"),
            # Year first: 2025 Feb 16
            (DAY, rf"{year4}{sep}{mon}(?P=sep){day}"),
            # Compact day first: 16Feb2025, 16Feb25
            (DAY, rf"(?<!\d)(?P<day>\d{{1,2}}){plain}(?P<year>\d{{4}}(?!\d)|{short})"),
            # Month and year: Feb 2025, Feb '25, febrero de 2025
            (MONTH, rf"{mon}{sep}{year_connector}{month_year}"),
            # Compact month and year: Mar2026
            (MONTH, rf"{plain}(?P<year>\d{{4}})(?!\d)"),
        ]
        self.formats = [(precision, re.compile(f, re.I)) for precision, f in self.formats]

    def month(self, word: str) -> int:
        return self.months[word.rstrip(".").lower()]


def alternation(words):
    """Regex alternation, longest first, so "sept" is tried before "sep"."""
    return "|".join(re.escape(w) for w in sorted(words, key=len, reverse=True))


ENGLISH = Language(
    full={
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6, "july": 7,
        "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    },
    abbreviated={
        "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
        "sept": 9, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    },
    ordinal="st|nd|rd|th",
    day_connector="of",
)

FRENCH = Language(
    full={
        "janvier": 1, "février": 2, "fevrier": 2, "mars": 3, "avril": 4, "mai": 5, "juin": 6,
        "juillet": 7, "août": 8, "aout": 8, "septembre": 9, "octobre": 10, "novembre": 11,
        "décembre": 12, "decembre": 12,
    },
    abbreviated={
        "janv": 1, "févr": 2, "fevr": 2, "avr": 4, "juil": 7, "sept": 9, "oct": 10, "nov": 11,
        "déc": 12, "dec": 12,
    },
    ordinal="er|ère",
    ordinal_on_first_only=True,
)

SPANISH = Language(
    full={
        "enero": 1, "febrero": 2, "marzo": 3, "abril": 4, "mayo": 5, "junio": 6, "julio": 7,
        "agosto": 8, "septiembre": 9, "setiembre": 9, "octubre": 10, "noviembre": 11,
        "diciembre": 12,
    },
    # No "set" for septiembre: too common an English word
    abbreviated={
        "ene": 1, "feb": 2, "mar": 3, "abr": 4, "may": 5, "jun": 6, "jul": 7, "ago": 8,
        "sep": 9, "oct": 10, "nov": 11, "dic": 12,
    },
    ordinal="º|o",
    day_connector="de",
    year_connector="de",
    ordinal_on_first_only=True,
)

LANGUAGES = [ENGLISH, FRENCH, SPANISH]


def numeric_candidates(filename: str, found: list, skipped: list):
    """The original numeric formats: year first, year last, and 8 digits."""
    # --- Pattern 1: 3-part, year first — YYYY<sep>XX<sep>XX ---
    # Backreference \2 enforces a consistent separator (. _ or -) throughout.
    # Lookarounds prevent matching inside a longer digit run.
    for m in re.finditer(r'(?<!\d)(\d{4})([._-])(\d{1,2})\2(\d{1,2})(?!\d)', filename):
        year = int(m.group(1))
        a = int(m.group(3))
        b = int(m.group(4))
        if not is_valid_year(year):
            continue
        if a > 12:
            # a cannot be a month; treat as YYYY-DD-MM
            date = try_date(year, b, a)
        else:
            # ISO 8601 convention: YYYY-MM-DD
            date = try_date(year, a, b)
        if date:
            found.append((DAY, m.start(), date))

    # --- Pattern 2: 3-part, year last — XX<sep>XX<sep>YYYY ---
    for m in re.finditer(r'(?<!\d)(\d{1,2})([._-])(\d{1,2})\2(\d{4})(?!\d)', filename):
        a = int(m.group(1))
        b = int(m.group(3))
        year = int(m.group(4))
        if not is_valid_year(year):
            continue
        if a > 12 and b <= 12:
            # a cannot be a month → DD-MM-YYYY
            date = try_date(year, b, a)
        elif b > 12 and a <= 12:
            # b cannot be a month → MM-DD-YYYY
            date = try_date(year, a, b)
        else:
            date = None
            if a <= 12 and b <= 12:
                skipped.append(
                    f"cannot determine if '{a:02d}' or '{b:02d}' is the month "
                    f"in '{filename}'"
                )
        if date:
            found.append((DAY, m.start(), date))

    # --- Pattern 3: 8-digit, no separator — YYYYMMDD or DDMMYYYY / MMDDYYYY ---
    for m in re.finditer(r'(?<!\d)(\d{8})(?!\d)', filename):
        s = m.group(1)

        # Try year-first (YYYYMMDD)
        year = int(s[:4])
        if is_valid_year(year):
            date = try_date(year, int(s[4:6]), int(s[6:8]))
            if date:
                found.append((DAY, m.start(), date))
                continue

        # Try year-last (DDMMYYYY or MMDDYYYY)
        year = int(s[4:])
        if is_valid_year(year):
            a = int(s[:2])
            b = int(s[2:4])
            date = None
            if a > 12 and b <= 12:
                # a cannot be a month → DD-MM-YYYY
                date = try_date(year, b, a)
            elif b > 12 and a <= 12:
                # b cannot be a month → MM-DD-YYYY
                date = try_date(year, a, b)
            elif a <= 12 and b <= 12:
                skipped.append(
                    f"cannot determine if '{a:02d}' or '{b:02d}' is the month "
                    f"in 8-digit sequence '{s}' from '{filename}'"
                )
            if date:
                found.append((DAY, m.start(), date))


def other_numeric_candidates(filename: str, found: list):
    """Scene-release dates, year and month, and bracketed years."""
    # Scene release: Site.YY.MM.DD.Title, always year first and set off by dots.
    # Inside a lookahead, so overlapping runs like .12.25.02.16. are all tried.
    for m in re.finditer(r"(?=(?<=[^.]\.)(\d{2})\.(\d{2})\.(\d{2})(?=\.[^.]))", filename):
        date = try_date(2000 + int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if date:
            found.append((DAY, m.start(), date))

    # Year and month: 2025-02. Not when more digits follow a separator, so a
    # rejected 2024-02-30 or 2024-05_17 is not read as a month.
    for m in re.finditer(r"(?<!\d)(?<!\d[._-])(\d{4})([._-])(\d{1,2})(?!\d)(?![._-]\d)", filename):
        year = int(m.group(1))
        month = int(m.group(3))
        if is_valid_year(year) and 1 <= month <= 12:
            found.append((MONTH, m.start(), f"{year:04d}-{month:02d}"))

    # Bracketed year: (2019) or [2019]
    for m in re.finditer(r"\((\d{4})\)|\[(\d{4})\]", filename):
        year = int(m.group(1) or m.group(2))
        if is_valid_year(year):
            found.append((YEAR, m.start(), f"{year:04d}"))


def month_name_candidates(filename: str, found: list):
    for language in LANGUAGES:
        for precision, pattern in language.formats:
            for m in pattern.finditer(filename):
                year = m.group("year").lstrip("'")
                year = int(year) if len(year) == 4 else 2000 + int(year)
                if not is_valid_year(year):
                    continue
                month = language.month(m.group("mon"))
                if precision == MONTH:
                    found.append((MONTH, m.start(), f"{year:04d}-{month:02d}"))
                    continue
                day = int(m.group("day"))
                if m.groupdict().get("ord") and language.ordinal_on_first_only and day != 1:
                    continue
                date = try_date(year, month, day)
                if date:
                    found.append((DAY, m.start(), date))


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
        log.warning(f"No time zone data for {FALLBACK_TIME_ZONE} (is tzdata installed?); skipping timestamps")
        return None


def timestamp_date(filename: str):
    """
    A Unix timestamp (10 digits, or 13 for milliseconds) that is the whole
    filename, or a prefix or suffix set off by a separator. Brackets do not
    count, so a "[original_<media id>]" suffix is never read as a date.
    """
    stamps = re.findall(r"^(\d{10}|\d{13})(?=[ ._-]|$)", filename)
    stamps += re.findall(r"(?<=[ ._-])(\d{10}|\d{13})$", filename)
    if not stamps:
        return None

    zone = local_zone()
    if zone is None:
        return None
    now = datetime.now(timezone.utc).timestamp()
    for stamp in stamps:
        seconds = int(stamp) / 1000 if len(stamp) == 13 else int(stamp)
        if TIMESTAMP_MIN <= seconds <= now:
            return datetime.fromtimestamp(seconds, zone).strftime("%Y-%m-%d")
    return None


def parse_date(filename: str):
    """
    Search a filename stem for a date in one of the supported formats.

    Every candidate is collected first. The most precise one wins (day, then
    month, then year), and the leftmost breaks ties. A Unix timestamp is used
    only when there is no other candidate.

    Returns YYYY-MM-DD, YYYY-MM or YYYY when a date is found unambiguously,
    or None otherwise.
    Logs a message when a candidate date is skipped due to ambiguity.
    """
    # One form for accented letters, so "février" matches however it was stored
    filename = unicodedata.normalize("NFC", filename)
    found = []
    skipped = []
    numeric_candidates(filename, found, skipped)
    other_numeric_candidates(filename, found)
    month_name_candidates(filename, found)

    if found:
        return min(found)[2]

    # Last resort: timestamps are too easily confused with media IDs to
    # compete with any other date
    date = timestamp_date(filename)
    if not date and skipped:
        log.info(f"Skipping ambiguous date: {skipped[0]}")
    return date


if __name__ == "__main__":
    fragment = json.loads(sys.stdin.read())
    scene_id = fragment.get("id", "unknown")

    if not fragment.get("files"):
        log.error(f"Scene {scene_id} has no files; cannot extract date from filename")
        print("null")
        sys.exit(0)

    path = fragment["files"][0]["path"]
    if len(fragment["files"]) > 1:
        log.debug(f"Scene {scene_id} has multiple files; using first: {path}")

    filename = os.path.splitext(os.path.basename(path))[0]
    date = parse_date(filename)

    if date:
        log.info(f"Scene {scene_id}: extracted date {date} from '{filename}'")
        print(json.dumps({"date": date}))
    else:
        log.info(f"Scene {scene_id}: no unambiguous date found in '{filename}'")
        print(json.dumps({}))
