# Stash Scrapers

Scrapers for [Stash](https://github.com/stashapp/stash), published as source indexes you can add to your Stash instance.

## Install

| Index | Branch | URL |
|---|---|---|
| Production | `main` | [https://visualhumanity.github.io/stash-scrapers/main/index.yml](https://visualhumanity.github.io/stash-scrapers/main/index.yml) |
| Develop | `develop` | [https://visualhumanity.github.io/stash-scrapers/develop/index.yml](https://visualhumanity.github.io/stash-scrapers/develop/index.yml) |

In Stash, go to **Settings > Metadata Providers** and add the production index URL as a source. The develop index holds pre-release builds for testing. Scrapers that need `py_common` get it from Stash's default Community (stable) source.

## Scrapers

| Scraper | Description |
|---|---|
| [VH - Convert HTML to Markdown](scrapers/ConvertHtmlToMarkdown/) | Converts an HTML scene description into Markdown, keeping links. Plain-text descriptions are left alone. |
| [VH - Extract Date from Filename](scrapers/DateFromFilename/) | Sets a scene's date from the video file's name, including written-out and partial dates in several languages. |
| [VH - File Metadata (ffprobe)](scrapers/FileMetadata/) | Reads title, URL, description, date and performer from a video file's embedded metadata with ffprobe. |
| [VH - Reddit (Gallery-DL)](scrapers/GalleryDlReddit/) | Fills scenes and images from the gallery-dl Reddit metadata file next to each file, falling back to the file name. |
| [VH - Gallery-DL - Twitter](scrapers/GalleryDlTwitter/) | Fills scenes and images from the gallery-dl Twitter metadata file next to each file. |
| [VH - Gay Erotic Video Index (GEVI)](scrapers/GEVI/) | Scrapes performers, scenes and groups from gayeroticvideoindex.com by URL. |
| [VH - OF-Scraper - User Data](scrapers/OFScraperUserData/) | Fills scenes from OF-Scraper's per-account database: title, date, performers, studio, URL and description. |
| [VH - OnlyFans](scrapers/OnlyFans/) | Scrapes performers and studios from an OnlyFans URL. |
| [VH - Twitter](scrapers/Twitter/) | Scrapes performers from Twitter, by profile URL or by name. |
| [VH - Title From Performers](scrapers/vhTitleFromPerformers/) | Sets a scene's title from its performers, for example `A & B`. |

Scrapers have no hand-set version. Each index shows the git short hash of the scraper's last commit.

## Development

- `develop` is the integration branch. Every push publishes the develop index, for testing on a test Stash instance.
- `main` is the release branch. It publishes the production index.
- Flow: feature branch, PR into `develop`, install from the develop index and test, then a release PR from `develop` into `main`.
- Every push to either branch rebuilds and republishes both indexes.
- No version bumps: the index version updates itself on every commit that touches a scraper.
- Full rules for agents and maintainers: [`CLAUDE.md`](CLAUDE.md).

## License

[AGPL-3.0](LICENCE)
