# Reddit (Gallery-DL)

Fills in a Stash **scene** or **image** from a [gallery-dl](https://github.com/mikf/gallery-dl) Reddit download. It reads the gallery-dl metadata file next to the media file and falls back to the file name when there is no usable one. Nothing is fetched from Reddit.

Actions: `sceneByFragment` and `imageByFragment` (use them from the scene/image "Scrape with..." menu or the Identify task).

## Data sources

For each file of the scene or image, in order, the scraper tries:

1. **The metadata file**: `<media file name>.json` next to the media (for example `clip.mp4` is described by `clip.mp4.json`, written by `gallery-dl --write-metadata`). It is used only when its gallery-dl `category` is `reddit`. A RedGIFs metadata file (`category` `redgifs`), an unreadable one, or one with no usable fields counts as not usable. `<media id>.info.json` files and a folder's `info.json` are never read.
2. **The file name**, when there is no usable metadata file.

The first file that yields a result wins.

## Metadata file mapping

| Stash field | Metadata key | Rule |
|---|---|---|
| title | `title` | The exact post title, trimmed. |
| date | `date`, else `created_utc` | The post's UTC date as `YYYY-MM-DD`. gallery-dl's `date` is `created_utc` written as UTC `YYYY-MM-DD HH:MM:SS`, the same date gallery-dl puts in file names, so no time zone conversion is done. |
| urls | `permalink` | `https://www.reddit.com` + permalink. |
| code | `id` | The post ID. |
| details | `selftext` | The post text, trimmed. Omitted when empty. |
| performers | `author` | One performer named `u_<author>` (the same name file-name scrapes give), with URL `https://www.reddit.com/user/<author>`. Omitted for `[deleted]` authors. |
| studio | `subreddit` | `r/<subreddit>` with URL `https://www.reddit.com/r/<subreddit>` and parent studio `Reddit`. |
| tags | `link_flair_text` | The post flair as one tag, as written (numbers included). Omitted when the post has none. |

Fields with nothing to say are left out entirely, so the scraper never blanks a value you set by hand.

Not mapped: direct media URLs, `over_18`, photographer.

## File name fallback

The scraper expects the gallery-dl file name format

```
<title> - <YYYY-MM-DD> - <performer>[ - <n>].<ext>
```

for example `Example Post - 2001-02-03 - u_example_user.mp4`, or `Example Post - 2001-02-03 - u_example_user - 2.jpg` for the second image of a gallery post.

| Stash field | Source |
|---|---|
| title | `<title>`, trimmed. File names are sanitized, so this can differ from the post title. |
| date | `<YYYY-MM-DD>` |
| performers | one performer named `<performer>` (gallery-dl's `u_<author>`). A `u_<author>` name gets the profile URL `https://www.reddit.com/user/<author>`, as on the metadata path; any other name gets no URL. |
| studio | from the folder the file is in, when it is named `r_<subreddit>`: same studio as above |

- The title may itself contain ` - `: the last ` - <YYYY-MM-DD> - ` in the name marks where the title ends.
- The trailing ` - <n>` gallery number is optional and is not part of any field.
- A performer name ending in digits (`u_example_user_1234`) is kept whole.
- The date must be a real calendar date.

## Behaviour

| Situation | Result | Log level |
|---|---|---|
| Several files | uses the first file with a usable metadata file or a matching name | |
| No usable metadata file and no matching name | `{}` (no update) | info |
| Metadata file unreadable or not a JSON object | file name fallback | warning |
| Metadata file holds non-Reddit data (RedGIFs) | file name fallback | debug |
| Scene has no files | `null` | error |
| Image input has no `id` | `null` | error |
| Image: GraphQL lookup failed (bad config, Stash unreachable) | `{}` | error, says "lookup failed" |
| Image: Stash returned no files for it | `{}` | warning, says "no files" |
| Success | the fields above | one info line naming the source |

## Image file paths

Where an image's file paths come from depends on the Stash build:

1. Stash builds that pass image file paths to scrapers (`files[].path` in the scrape input, newer than v0.31.1) need nothing else. The scraper uses those paths and makes no GraphQL call.
2. Older builds, v0.31.1 included, send only the image ID. The scraper then asks Stash's GraphQL API for the image's files, using `py_common`, and tries every path returned.

## Setup

1. Add this repository's scraper source index in Stash under Settings > Metadata Providers > Available Scrapers, then install **VH - Reddit (Gallery-DL)** and its dependency **py_common**.
2. **Scenes need nothing else.** Neither do images on Stash builds that pass image file paths.
3. **Images on older Stash builds need a `py_common` config.** Create or edit `py_common/config.ini` inside Stash's scrapers folder (`scrapers/py_common/config.ini` under your Stash configuration directory) and set:

   ```ini
   url = http://localhost:9999
   api_key = <your Stash API key>
   ```

   Generate the key under Settings > Security > Authentication. `py_common` creates this file with an empty `api_key` the first time an image is scraped. If the key is missing or wrong, `py_common` logs an error naming `config.ini`, the scraper logs "lookup failed" and returns no update.

## Tests

From this directory: `python3 -B -m unittest -v`. The tests run the script as a subprocess with made-up metadata files, file names and a fake GraphQL module; they never contact Stash.
