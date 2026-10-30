# VH - Reddit (Gallery-DL)

Fills a scene or an image from a [gallery-dl](https://github.com/mikf/gallery-dl) Reddit download: from the gallery-dl metadata file next to the media file, or from the file name when there is no usable metadata file. Nothing is fetched from Reddit.

## Supports

- **Scene** (by fragment): title, date, urls, code, details, performers, studio, tags
- **Image** (by fragment): the same fields

From the file name, only title, date, performers and studio are filled. Not filled: direct media URLs, `over_18`, photographer.

## Data sources

The scraper tries two sources:

1. **The metadata file**: `<media file name>.json` next to the media, written by `gallery-dl --write-metadata` (`clip.mp4` is described by `clip.mp4.json`). It is used only when its gallery-dl `category` is `reddit`. A RedGIFs metadata file (`category` `redgifs`), an unreadable one or one with no usable fields counts as not usable. `<media id>.info.json` files and a folder's `info.json` are never read. Images 2 to N of a gallery post have no metadata file of their own and use image 1's (see [Gallery posts](#gallery-posts)).
2. **The file name**, when there is no usable metadata file.

With several files, the metadata files of all of them are tried first, in order, and only then their file names. So an old-format duplicate without a metadata file never beats a file that has one.

## File name fallback

The scraper expects the gallery-dl file name format

```
<title> - <YYYY-MM-DD> - <performer>[ - <n>].<ext>
```

for example `Example Post - 2001-02-03 - u_example_user.mp4`, or `Example Post - 2001-02-03 - u_example_user - 2.jpg` for the second image of a gallery post.

- **title**: `<title>`, plus ` [n]` for gallery files (see [Gallery posts](#gallery-posts)). File names are sanitized, so this can differ from the post title. The title may itself contain ` - `: the last ` - <YYYY-MM-DD> - ` in the name marks where it ends.
- **date**: `<YYYY-MM-DD>`, which must be a real calendar date.
- **performers**: one performer named `<performer>` (gallery-dl's `u_<author>`). A `u_<author>` name gets the profile URL `https://www.reddit.com/user/<author>`, as from a metadata file; any other name gets no URL. A name ending in digits (`u_example_user_1234`) is kept whole. Left out for `u_[deleted]`.
- **studio**: from the folder the file is in, when it is named `r_<subreddit>`: the same studio as from a metadata file.

## Gallery posts

gallery-dl numbers the files of a multi-image post with a ` - <n>` suffix (`... - 1.jpg`, `... - 2.jpg`, ...) and writes a metadata file for image 1 only.

- **Borrowing:** a file numbered 2 or more with no metadata file of its own uses image 1's: the same file name with ` - 1`, in the same folder. Image 1 with the same extension is tried first, then image 1 with any other extension. A RedGIFs or unreadable metadata file of the file's own is not replaced by image 1's. If neither file is usable, the file name is used.
- **Numbering:** `n` is the file name's ` - <n>` suffix and `N` the number of items in the metadata's `gallery_data.items`.
  - With a metadata file where `N` is 2 or more: `<post title> [n/N]` (image 1 gets `[1/N]`).
  - With a metadata file without `gallery_data` (or deleted), or from the file name, for a file numbered 1 or more: `<title> [n]`.
  - A one-item gallery (`N` is 1), the suffix ` - 0` (gallery-dl's number for single-image posts), no suffix, or a file name not in the format above: the plain title.
  - A post with no title gets no bare number.

## Field notes

From a metadata file:

- **title**: the exact post title, numbered for gallery posts (see [Gallery posts](#gallery-posts)).
- **date**: the post's UTC date, from `date`, else `created_utc`. gallery-dl's `date` is `created_utc` written as UTC `YYYY-MM-DD HH:MM:SS`, the same date gallery-dl puts in file names, so no time zone conversion is done.
- **urls**: `https://www.reddit.com` plus the post's `permalink`.
- **performers**: one performer named `u_<author>` (the same name a file name gives), with URL `https://www.reddit.com/user/<author>`. Left out for `[deleted]` authors.
- **studio**: `r/<subreddit>` with URL `https://www.reddit.com/r/<subreddit>` and parent studio `Reddit`.
- **tags**: the post flair (`link_flair_text`) as one tag, as written (numbers included).

A field with nothing to fill is left out, so the scraper never blanks a value set by hand.

## Configuration

- Images on Stash v0.31.1 and older need `py_common` set up as in the root README's [Install section](../../README.md#configure-py_common). Those builds pass an image scraper only the image ID, so the scraper asks Stash's GraphQL API for the image's files and tries every path returned. Newer builds pass the file paths (`files[].path`) and need nothing, as do scenes.

## Known limitations

- No usable metadata file and no file name in the expected format gives no update.
- An unreadable metadata file, or one that is not a JSON object, logs a warning and falls back to the file name.
- A scene with no files fails the scrape. So does an image scrape input with no ID.
- An image whose GraphQL lookup fails (bad `config.ini`, Stash unreachable) gives no update and logs an error saying "lookup failed". One for which Stash returns no files gives no update and logs a warning saying "no files".

## Development

- Tests: `python3 -B -m unittest -v` from this folder. They run the script as a subprocess with made-up metadata files, file names and a fake GraphQL module; they never contact Stash.
- Each successful scrape logs one Info line naming its source. Text values in log lines are cut to 80 characters, since Stash 0.31.1 closes the scraper's stderr on a line over 64 KiB.
- A RedGIFs metadata file is skipped at Debug level.
