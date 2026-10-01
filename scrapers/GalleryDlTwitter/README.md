# Gallery-DL - Twitter

Fills in a Stash **scene** or **image** from the [gallery-dl](https://github.com/mikf/gallery-dl) JSON sidecar that sits next to a downloaded Twitter/X media file. Galleries and groups are not supported.

It reads `<media file>.json` (for example `clip.mp4` is described by `clip.mp4.json`, written by `gallery-dl --write-metadata`). The `<cdn key>.info.json` duplicates and the per-directory `info.json` are ignored. Nothing is fetched from Twitter.

Actions: `sceneByFragment` and `imageByFragment` (use them from the scene/image "Scrape with..." menu or the Identify task).

## What it fills in

Scenes and images get the same fields:

| Stash field | Sidecar source | Rule |
|---|---|---|
| title | `content`, `num`, `count` | First non-empty line of the caption, trimmed. If the tweet has more than one media item (`count > 1`), ` [i]` is appended, where `i` is `num`. The whole title is capped at 120 characters: the caption is cut at a word boundary and ends in `…`, leaving room for the suffix. No caption means no title (and no suffix). |
| details | `content` | The full caption, trimmed, emoji kept. Omitted when empty. |
| date | `date` | gallery-dl dates are UTC. Converted to the container's own `TZ` (America/Toronto if `TZ` is unset or unknown), then written as `YYYY-MM-DD`. |
| code | `tweet_id` | The tweet ID as plain text. Tweet IDs are time-ordered, so sorting by code is chronological, except that Stash sorts the code as text, so an ID with fewer digits sorts before a longer one. |
| urls | `tweet_id` + poster handle | One permalink: `https://twitter.com/<handle>/status/<tweet_id>`. Without a handle: `https://twitter.com/i/status/<tweet_id>`. |
| performers | `author.name`, else `user.name` | One performer named by the poster handle, with `https://twitter.com/<handle>` as its URL. No aliases. |
| studio | same handle | A studio named by the poster handle, with the same profile URL. |
| tags | `hashtags` | Each hashtag as given (without `#`), de-duplicated case-insensitively. Omitted when the post has none. No fixed tags are added. |

Fields with nothing to say are left out entirely. The scraper never sends an empty string or list, so it cannot blank out a value you set by hand.

Not mapped: cover image, director, photographer, groups, alt text (`description`), reply/quote/retweet info, language, the sensitive flag and the like/view counts.

Stash links a scraped performer or studio to an existing one only by exact name, then exact alias. Handles rarely match real-name performers, so expect new entries unless you add the handle as an alias. Identify only creates them if "create missing" is on for that type.

## Behaviour

| Situation | Result | Log level |
|---|---|---|
| No sidecar next to the file | `{}` (no update) | debug |
| Avatar or background sidecar (not a post) | `{}` | debug |
| Sidecar is unreadable or not valid JSON | `{}` | warning |
| Scene has no files | `null` | error |
| Image: Stash returns no files for it | `{}` | warning |
| Several files | uses the first file that has a sidecar | |
| A field is missing from the sidecar | only that field is left out | |
| Success | the fields above | one info line naming the sidecar |

A missing `TZ` or an unknown time zone is not an error: the scraper quietly uses America/Toronto and only logs at debug level.

## Setup

1. Add this repository's scraper source index in Stash under Settings > Metadata Providers > Available Scrapers, then install **Gallery-DL - Twitter** and its dependency **py_common**. The container needs Python 3 with `tzdata` for the time zone conversion.
2. **Scenes need nothing else.**
3. **Images need a `py_common` config.** Stash does not give an image scraper the file path (only the image ID), so the scraper asks Stash's GraphQL API for it, using `py_common`. Create or edit `py_common/config.ini` inside Stash's scrapers folder (`scrapers/py_common/config.ini` under your Stash configuration directory) and set only what this scraper depends on:

   ```ini
   url = http://localhost:9999
   api_key = <your Stash API key>
   ```

   Generate the key under Settings > Security > Authentication. `py_common` creates this file with an empty `api_key` the first time an image is scraped. If the key is missing or wrong, `py_common` logs an error naming `config.ini` and the scraper returns no update.

## Tests

From this directory: `python3 -B -m unittest -v`. The tests use synthetic sidecars and never contact Stash.
