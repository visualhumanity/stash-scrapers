# VH - File Metadata (ffprobe)

Fills a scene from the metadata tags embedded in its video file, read with ffprobe.

Requires: [ffprobe](https://ffmpeg.org/ffprobe.html), on the `PATH` where Stash runs scrapers.

## Supports

- **Scene** (by fragment): title, url, details, date, performers, studio

## Field notes

Tag names are matched in any letter case.

- **url**: from the `comment` tag, only when it starts with a URL scheme such as `https:`.
- **details**: from the `description` tag, as is. HTML is not converted; [VH - Convert HTML to Markdown](../ConvertHtmlToMarkdown/) can do that afterward.
- **date**: from the `creation_time` tag when present, otherwise the `date` tag. `creation_time` is cut to its first 10 characters, so the day is the one in the tag's own time zone (usually UTC), and it is often when the file was encoded rather than recorded.
- **performers** and **studio**: both named after the `artist` tag.

## Known limitations

- Only the scene's first file is read.
- A `comment` that starts with a word and a colon, such as `Note: example`, is taken as a URL too.
- A file with no metadata tags, a file ffprobe cannot read, ffprobe missing from the `PATH`, or a `date` tag Python's `datetime.fromisoformat()` cannot read (such as `2025` alone) fails the scrape with a Python error in the log.

## Development

- No tests. To try it by hand, pipe `{"id": "1", "files": [{"path": "/data/example/video.mp4"}]}` into `python3 FileMetadata.py` from this folder.
