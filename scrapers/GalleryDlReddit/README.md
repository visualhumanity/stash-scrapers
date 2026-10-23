# Reddit (Gallery-DL)

Fills in a Stash **scene** or **image** from the file name [gallery-dl](https://github.com/mikf/gallery-dl) gives a downloaded Reddit post. Nothing is fetched from Reddit and no gallery-dl metadata file is read yet.

Actions: `sceneByFragment` and `imageByFragment` (use them from the scene/image "Scrape with..." menu or the Identify task).

## File names

The scraper expects the gallery-dl file name format

```
<title> - <YYYY-MM-DD> - <performer>[ - <n>].<ext>
```

for example `Example Post - 2001-02-03 - u_example_user.mp4`, or `Example Post - 2001-02-03 - u_example_user - 2.jpg` for the second image of a gallery post. Only the file name is read, never the folders.

- The title may itself contain ` - `: the last ` - <YYYY-MM-DD> - ` in the name marks where the title ends.
- The trailing ` - <n>` gallery number is optional and is not part of any field.
- A performer name ending in digits (`u_example_user_1234`) is kept whole.
- The date must be a real calendar date.

## What it fills in

Scenes and images get the same fields:

| Stash field | Source |
|---|---|
| title | `<title>`, trimmed |
| date | `<YYYY-MM-DD>` |
| performers | one performer named `<performer>` (gallery-dl's `u_<author>`) |

## Behaviour

| Situation | Result | Log level |
|---|---|---|
| Several files | uses the first file whose name matches | |
| No file name matches | `{}` (no update) | info |
| Scene has no files | `null` | error |
| Image input has no `id` | `null` | error |
| Image: GraphQL lookup failed (bad config, Stash unreachable) | `{}` | error, says "lookup failed" |
| Image: Stash returned no files for it | `{}` | warning, says "no files" |
| Success | the fields above | one info line naming the file |

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

From this directory: `python3 -B -m unittest -v`. The tests run the script as a subprocess with made-up file names and a fake GraphQL module; they never contact Stash.
