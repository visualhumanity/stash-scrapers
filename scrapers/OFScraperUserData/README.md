# OF-Scraper - User Data

Scene scraper (`sceneByFragment`) for videos downloaded by OF-Scraper. It reads the per-account `user_data.db` that OF-Scraper keeps, so it works from the scene edit tab ("Scrape with") and from the Identify task. The database is only ever opened read-only.

## Fields

| Field | Source |
|-------|--------|
| Date | `created_at` of the post, message or story, converted from UTC to the container time zone (`TZ`), `YYYY-MM-DD` |
| Studio | account username from the model folder name |
| Performers | display name from the model folder name, plus every account mentioned in the description |
| URL | `https://onlyfans.com/<post id>/<username>`, posts only (timeline, archived, pinned, paid); none for messages and stories |
| Description | post text converted from HTML to Markdown by the `ConvertHtmlToMarkdown` scraper's converter; relative links (`/name`) become `https://onlyfans.com/name`; plain text is left as is |
| Title | inferred from the description (OnlyFans has no titles), see below; not set when there is no usable text |

Director, galleries and tags are not set.

## Title inference

1. HTML is stripped (`<br>`, `</p><p>` become line breaks, entities decoded, `**` and `__` removed).
2. Per line, filler is removed: link pointers (`link in bio`, `link below`), tip asks (`tip $5 ...`, `tip menu`), thanks (`thanks for subscribing`), calls to action (`subscribe now`, `DM me`), `stream started at ...`, and `FREE:` or `12 MIN -` prefixes. Bare greetings stay.
3. The first line with usable text is used. If none is left (empty, emoji only, only filler) no title is set.
4. The line is split into segments that end at an emoji run (kept whole) or at `. ! ? ... 。 ！ ？`. A period after `pt min vs ft no dr mr mrs st` or inside a number does not end a segment.
5. Segments are joined from the left until the title is 30 characters long.
6. Over 90 characters, the title is cut at a word boundary and ends with `…`.
7. Bare URLs, trailing `, ; : - –` and one trailing period are removed; `!`, `?`, `...` and emoji are kept.
8. A title with no lowercase letters is converted to title case (acronyms such as `POV` and `PT` stay uppercase).

The description keeps the full text.

This scraper depends on the **VH - Convert HTML to Markdown** scraper (installed automatically as a requirement). If it is missing, descriptions stay as raw HTML and a warning is logged.

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

The media ID is read from names in either format. The new format must match as a whole (a cut-off older name can end in `_<digits>.<ext>` where the digits are only part of an ID). When the name has no media ID, or the ID is not in the database, the file is matched on the `filename` and the end of the `directory` OF-Scraper stored for it (`<model folder>/<type>/<media>`). Only that end is compared, because OF-Scraper and Stash usually mount the download root at different paths. A folder without `(username)` is used as both performer and studio.

## Mentions

`@name`, `href="/name"` and `onlyfans.com/name` in the description become performers (leading `@` stripped, duplicates and the account's own username dropped). Add the usernames as performer aliases in Stash so they resolve to existing performers.

## Database discovery

The database named after the folder's username is tried first. If it does not hold the file, every `.data/*/user_data.db` is scanned, and a hit is remembered in `cache_db_location.json` (next to the script, git-ignored) so the scan happens once per folder. Misses are never cached and stale entries are discarded.

## Time zone

Set `TZ` on the Stash container. Without it the scraper falls back to `America/Toronto`.

## Tests

`python -B -m unittest test_OFScraperUserData` from this folder (needs the sibling `ConvertHtmlToMarkdown` folder). They build fake download roots with synthetic databases.
