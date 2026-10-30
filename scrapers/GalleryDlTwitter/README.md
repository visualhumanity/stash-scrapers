# VH - Gallery-DL - Twitter

Fills a scene or an image from the [gallery-dl](https://github.com/mikf/gallery-dl) metadata file next to a downloaded Twitter/X media file. Nothing is fetched from Twitter.

Requires: Python time zone data where Stash runs scrapers, from the system or the [`tzdata`](https://pypi.org/project/tzdata/) package.

## Supports

- **Scene** (by fragment): title, details, date, code, urls, performers, studio, tags
- **Image** (by fragment): the same fields

Not filled: cover image, director, photographer, groups, alt text (`description`), reply, quote and retweet info, language, the sensitive flag, like and view counts.

## Metadata files

The scraper reads `<media file>.json`, written by `gallery-dl --write-metadata`: `clip.mp4` is described by `clip.mp4.json`. The `<cdn key>.info.json` duplicates and a folder's `info.json` are ignored. With several files, the first file that has a metadata file is used. Metadata files for profile pictures and banners (`subcategory` `avatar` or `background`) are not posts and give no update.

## Field notes

- **title**: the first non-empty line of the caption. When the tweet has more than one media item, ` [i]` is appended, `i` being the item's `num`. The whole title is capped at 120 characters: the caption is cut at a word boundary and ends in `…`, leaving room for the suffix. No caption means no title.
- **details**: the full caption, emoji kept.
- **date**: gallery-dl dates are UTC. The date is converted to the time zone in the `TZ` environment variable of the Stash process, or to a fallback zone set in the script when `TZ` is unset or unknown, then written as `YYYY-MM-DD`. Near midnight, the day depends on that zone.
- **code**: the tweet ID. Tweet IDs are time-ordered, but Stash sorts the code as text, so an ID with fewer digits sorts before a longer one.
- **urls**: `https://twitter.com/<handle>/status/<tweet_id>`, or `https://twitter.com/i/status/<tweet_id>` without a handle.
- **performers** and **studio**: both named after the poster's handle (`author.name`, else `user.name`), with `https://twitter.com/<handle>` as their URL. Stash links a scraped performer or studio to an existing one only by exact name, then exact alias, so expect new entries unless the handle is an alias. Identify creates them only when "Create missing" is on for that type.
- **tags**: the hashtags, without `#`, de-duplicated in any letter case. No fixed tags are added.

A field with nothing to fill is left out, so the scraper never blanks a value set by hand.

## Configuration

- Images need `py_common` set up as in the root README's [Install section](../../README.md#configure-py_common): Stash passes an image scraper only the image ID, so the scraper asks Stash's GraphQL API for the file path. Scenes need nothing.

## Known limitations

- A media file with no metadata file, or an unreadable one, gives no update. An unreadable metadata file, or one that is not a JSON object, logs a warning.
- Without time zone data for the fallback zone, the date is left out with a warning.
- A scene with no files fails the scrape. So does an image scrape input with no ID.
- An image whose GraphQL lookup fails, or for which Stash returns no files, gives no update.

## Development

- Tests: `python3 -B -m unittest -v` from this folder. They use synthetic metadata files and never contact Stash.
- A missing `TZ` or an unknown time zone is logged at Debug level only. Each successful scrape logs one Info line naming the metadata file.
