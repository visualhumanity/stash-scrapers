# VH - Extract Date from Filename

Sets a scene's date from its video file's name. Reads numeric dates, written-out dates in English, French and Spanish, partial dates and, as a last resort, Unix timestamps.

## Supports

- **Scene** (by fragment): date

## Date formats

Only the file name is read, without its extension. Folder names are ignored. All examples below read as `2025-02-16` unless noted.

- Year first: `2025-02-16`, `2025.2.16`, `2025_16_02` (day in the middle when it is above 12). The separator is `.`, `_` or `-`, the same throughout.
- Year last: `16-02-2025` or `02.16.2025`, only when the day is above 12.
- Eight digits: `20250216`, `16022025` or `02162025`.
- Scene release, year first between dots, with text on both sides: `Example.25.02.16.Scene`.
- Month names, in any letter case, separated by spaces, `.`, `_` or `-` (`16_Feb_2025`):
  - English: `Feb 16, 2025`, `16 Feb 2025`, `16th of February 2025`, `2025 Feb 16`, `16Feb2025`, `16 Feb 25`.
  - French: `16 février 2025`, `16 févr. 2025`, `1er mars 2025` (`2025-03-01`). Accents are optional.
  - Spanish: `16 de febrero de 2025`, `febrero 16, 2025`, `1º de marzo de 2025` (`2025-03-01`).
- Month and year (`2025-02`): `Feb 2025`, `Feb '25`, `febrero de 2025`, `Feb2025`, `2025-02`.
- Year (`2025`): `(2025)` or `[2025]`.
- Unix timestamp, in seconds or milliseconds, as the whole name or set off at its start or end: `1739707200`, `Example Scene_1739707200000`.

## Field notes

- **date**:
  - A month and year or a bracketed year fills a partial date, which Stash stores with month or year precision.
  - With several dates in the name, a full date beats a month and year, which beats a year. Among equals, the leftmost wins. `Example Scene 2024-11 2025-02-16` gives `2025-02-16`.
  - A timestamp is used only when no other date is found. It becomes a day in the time zone set by the `TZ` environment variable of the Stash process, or in a fallback zone set in the script when `TZ` is unset or unknown. Near midnight, the day depends on that zone.

## Known limitations

- Year-last dates where both numbers could be the month, such as `05-06-2025`, are skipped as ambiguous. So are eight digits like `05062025`.
- Eight digits are never read as year, day, month: `20251602` gives nothing.
- An invalid date does not fall back to its month: `30 Feb 2025` and `2025-02-30` give nothing.
- Spaces do not separate numeric dates: `2025 02 16` gives nothing.
- Two-digit years are read as 2000 to 2099. Years outside 1900 to 2100 are ignored.
- `Feb 25` gives nothing, since `25` could be a day. Write `Feb '25` or `Feb 2025`.
- Timestamps before 2000 or in the future are ignored, as are timestamps in the middle of the name or in brackets.
- French and Spanish ordinals are allowed only on the first of the month: `1er mars 2025` works, `2er mars 2025` gives nothing.
- Without Python time zone data (from the system or the [`tzdata`](https://pypi.org/project/tzdata/) package), timestamps are skipped with a warning.
- Only the scene's first file is read.
- When nothing is found, the scene is left unchanged.

## Development

- Tests: `python3 -B -m unittest -v` from this folder. They use made-up file names and run the script as a subprocess for the input and output checks; they never contact Stash.
- `parse_date()` collects candidates from every format, then applies the precedence under Field notes. Each language is a `Language` object with its month words, ordinals and connector words.
- When nothing is found, an Info log line names the leftmost candidate that was skipped and why.
