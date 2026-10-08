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

This scraper depends on the **Convert HTML to Markdown** scraper (installed automatically as a requirement). If it is missing, descriptions stay as raw HTML and a warning is logged.

## Expected layout

```
<download root>/<Display Name> (<username>)/<Posts|Messages|Archived|Stories>/<Videos|Images>/<file>
<download root>/.data/<username>_<account id>/user_data.db
```

The media ID is read from the end of the file name (`... [<original name>_<media id>].<ext>`). A folder without `(username)` is used as both performer and studio.

## Mentions

`@name`, `href="/name"` and `onlyfans.com/name` in the description become performers (leading `@` stripped, duplicates and the account's own username dropped). Add the usernames as performer aliases in Stash so they resolve to existing performers.

## Database discovery

The database named after the folder's username is tried first. If it does not hold the media ID, every `.data/*/user_data.db` is scanned, and a hit is remembered in `cache_db_location.json` (next to the script, git-ignored) so the scan happens once per folder. Misses are never cached and stale entries are discarded.

## Time zone

Set `TZ` on the Stash container. Without it the scraper falls back to `America/Toronto`.

## Known limitation

OF-Scraper truncates long file names, which can cut off the `_<media id>]` suffix. Those files cannot be matched and return an empty result. Shortening the OF-Scraper `file_format` text length avoids this.

## Tests

`python -B -m unittest test_OFScraperUserData` from this folder (needs the sibling `ConvertHtmlToMarkdown` folder). They build fake download roots with synthetic databases.
