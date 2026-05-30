import json
import os
import re
import sys
from datetime import datetime

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


def is_valid_year(y: int) -> bool:
    return YEAR_MIN <= y <= YEAR_MAX


def try_date(year: int, month: int, day: int):
    """Return YYYY-MM-DD string if the combination is a valid calendar date, else None."""
    try:
        return datetime(year, month, day).strftime("%Y-%m-%d")
    except ValueError:
        return None


def parse_date(filename: str):
    """
    Search a filename stem for a date in one of the supported formats.

    Accepted separators: period, underscore, or hyphen (must be consistent within a date).
    Spaces are never treated as separators.

    Returns a YYYY-MM-DD string when a date is found unambiguously, or None otherwise.
    Logs a message when a candidate date is skipped due to ambiguity.
    """
    # Stores the first ambiguous case found (logged only if no valid date is returned).
    first_ambiguous_msg = None

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
            return date

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
            if date:
                return date
        elif b > 12 and a <= 12:
            # b cannot be a month → MM-DD-YYYY
            date = try_date(year, a, b)
            if date:
                return date
        elif a <= 12 and b <= 12 and first_ambiguous_msg is None:
            first_ambiguous_msg = (
                f"cannot determine if '{a:02d}' or '{b:02d}' is the month "
                f"in '{filename}'"
            )

    # --- Pattern 3: 8-digit, no separator — YYYYMMDD or DDMMYYYY / MMDDYYYY ---
    for m in re.finditer(r'(?<!\d)(\d{8})(?!\d)', filename):
        s = m.group(1)

        # Try year-first (YYYYMMDD)
        year = int(s[:4])
        if is_valid_year(year):
            date = try_date(year, int(s[4:6]), int(s[6:8]))
            if date:
                return date

        # Try year-last (DDMMYYYY or MMDDYYYY)
        year = int(s[4:])
        if is_valid_year(year):
            a = int(s[:2])
            b = int(s[2:4])
            if a > 12 and b <= 12:
                # a cannot be a month → DD-MM-YYYY
                date = try_date(year, b, a)
                if date:
                    return date
            elif b > 12 and a <= 12:
                # b cannot be a month → MM-DD-YYYY
                date = try_date(year, a, b)
                if date:
                    return date
            elif a <= 12 and b <= 12 and first_ambiguous_msg is None:
                first_ambiguous_msg = (
                    f"cannot determine if '{a:02d}' or '{b:02d}' is the month "
                    f"in 8-digit sequence '{s}' from '{filename}'"
                )

    if first_ambiguous_msg:
        log.info(f"Skipping ambiguous date: {first_ambiguous_msg}")

    return None


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
