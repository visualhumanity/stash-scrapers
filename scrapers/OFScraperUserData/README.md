# VH - OF-Scraper - User Data

Fills a scene downloaded by [OF-Scraper](https://github.com/datawhores/OF-Scraper) from the per-account `user_data.db` that OF-Scraper keeps. It works from the scene edit tab ("Scrape with") and from the Identify task. The database is only ever opened read-only.

Requires: [VH - Convert HTML to Markdown](../ConvertHtmlToMarkdown/), and Python time zone data where Stash runs scrapers, from the system or the [`tzdata`](https://pypi.org/project/tzdata/) package.

## Supports

- **Scene** (by fragment): title, date, urls, details, performers, studio

Not filled: director, galleries, tags.

## Expected layout

```
<download root>/<Display Name> (<username>)/<Posts|Messages|Archived|Stories>/<Videos|Images>/<file>
<download root>/.data/<username>_<account id>/user_data.db
```

### File names

Recommended OF-Scraper `file_options`:

```json
"file_format": "{date}_{post_id}_{original_filename}_{media_id}.{ext}",
"date": "YYYY-MM-DD"
```

The `date` setting is required: OF-Scraper's default is `MM-DD-YYYY`, and names with that date are not read as this format (they still match through the fallback below when OF-Scraper stored the same name).

For example `2001-02-03_1000000001_0a1b2c3d4e5f6g7h8i9j0_source_2000000001.mp4`: the post date (`YYYY-MM-DD`, UTC as OF-Scraper formats it), the post ID, the OnlyFans CDN file name without its extension (`<id>_source` for videos, `<id>` for DRM videos, `<width>x<height>_<hash>` for images) and the media ID. Files of one post sort together and each has its own media ID.

- The media ID comes last, right before the extension. That ending (`_<digits>.<ext>`) is the only one OF-Scraper keeps when it shortens a long name, and it makes the ID easy to find.
- There is no post text. OF-Scraper counts about 2 bytes per ASCII character against a 254-byte limit, so names with text are often cut, and the cut removes the media ID of the older format below. Names in this format stay under 100 characters.

The older `{date} - {text} [{original_filename}_{media_id}].{ext}` format is still supported, so existing files do not need renaming.

The media ID is read from names in either format. The new format must match as a whole (a cut-off older name can end in `_<digits>.<ext>` where the digits are only part of an ID). When the name has no media ID, or the ID is not in the database, the file is matched on the `filename` and the end of the `directory` OF-Scraper stored for it (`<model folder>/<type>/<media>`). Only that end is compared, because OF-Scraper and Stash usually mount the download root at different paths.

## Database discovery

The database named after the folder's username is tried first. If it does not hold the file, every `.data/*/user_data.db` is scanned, and a hit is remembered in `cache_db_location.json` (next to the script, git-ignored) so the scan happens once per folder. Misses are never cached and stale entries are discarded.

## Title inference

OnlyFans posts have no titles, so the title is inferred from the description:

1. HTML is stripped (`<br>`, `</p><p>` become line breaks, entities decoded, `**` and `__` removed).
2. Per line, filler is removed: link pointers (`link in bio`, `link below`), tip asks (`tip $5 ...`, `tip menu`), thanks (`thanks for subscribing`), calls to action (`subscribe now`, `DM me`), `stream started at ...`, and `FREE:` or `12 MIN -` prefixes. Bare greetings stay.
3. The first line with usable text is used. If none is left (empty, emoji only, only filler) no title is set.
4. The line is split into segments that end at an emoji run (kept whole) or at `. ! ? ... 。 ！ ？`. A period after `pt min vs ft no dr mr mrs st` or inside a number does not end a segment.
5. Segments are joined from the left until the title is 30 characters long.
6. Over 90 characters, the title is cut at a word boundary and ends with `…`.
7. Bare URLs, trailing `, ; : - –` and one trailing period are removed; `!`, `?`, `...` and emoji are kept.
8. A title with no lowercase letters is converted to title case (acronyms such as `POV` and `PT` stay uppercase).

## Field notes

- **title**: see [Title inference](#title-inference).
- **date**: `created_at` of the post, message or story, converted from UTC to the time zone in the `TZ` environment variable of the Stash process (see [Configuration](#configuration)).
- **urls**: `https://onlyfans.com/<post id>/<username>`, for posts only (timeline, archived, pinned, paid); none for messages and stories.
- **details**: the full post text, converted from HTML to Markdown by [VH - Convert HTML to Markdown](../ConvertHtmlToMarkdown/). Relative links (`/name`) become `https://onlyfans.com/name`; plain text is left as is.
- **performers**: the display name from the model folder name, plus every account mentioned in the description: `@name`, `href="/name"` and `onlyfans.com/name` (leading `@` stripped, duplicates and the account's own username dropped). Add the usernames as performer aliases in Stash so they resolve to existing performers.
- **studio**: the account username from the model folder name. A folder without `(username)` is used as both performer and studio.

## Configuration

- Set the `TZ` environment variable in the environment Stash runs in (for Docker, the container's environment). Without it, the scraper falls back to a zone set in the script.

## Known limitations

- Only the scene's first file is read.
- A file outside the expected layout, or not found in any database, gives no update.
- If VH - Convert HTML to Markdown is missing, descriptions stay as raw HTML and a warning is logged.
- An unknown `TZ`, or no time zone data for the zone in use, fails the scrape with an error in the log.

## Development

- Tests: `python3 -B -m unittest -v` from this folder (needs the sibling `ConvertHtmlToMarkdown` folder). They build fake download roots with synthetic databases; they never contact Stash.
