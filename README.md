# Stash Scrapers

Scrapers for [Stash](https://github.com/stashapp/stash), published as source indexes you can add to your Stash instance.

## Install

| Index | Branch | URL |
|---|---|---|
| Production | `main` | [https://visualhumanity.github.io/stash-scrapers/main/index.yml](https://visualhumanity.github.io/stash-scrapers/main/index.yml) |
| Develop | `develop` | [https://visualhumanity.github.io/stash-scrapers/develop/index.yml](https://visualhumanity.github.io/stash-scrapers/develop/index.yml) |

In Stash, go to **Settings > Metadata Providers** and add the production index URL as a source. The develop index holds pre-release builds for testing. Scrapers that need `py_common` get it from Stash's default Community (stable) source.

### Configure py_common

Scrapers that ask Stash's GraphQL API for data Stash does not pass them (for example an image's file path) do so through `py_common`, which reads the Stash URL and API key from its `config.ini`. A scraper whose README links here needs this step.

1. Find the file. It sits in the `py_common` folder itself, next to `py_common`'s own code. With the Community source's default local path that is `scrapers/community/py_common/config.ini` under your Stash configuration directory (not `scrapers/py_common/`). `py_common` creates it, with `url = http://localhost:9999` and an empty `api_key`, the first time a scraper that uses it runs.
2. Set:

   ```ini
   url = http://localhost:9999
   api_key = <your Stash API key>
   ```

   `url` must point to your Stash server. `api_key` is needed when Stash authentication is on; generate it under Settings > Security > Authentication. `py_common` also needs the Python `requests` package wherever Stash runs scrapers.
3. To confirm the path, set Stash's log level to Debug (Settings > System > Logging), run the scrape once, then open Settings > Logs with the Debug filter. `py_common` logs one of:

   ```
   [py_common/graphql.py] First run, creating default config at <path>/config.ini
   [py_common/graphql.py] Reading config from <path>/config.ini
   ```

   That `<path>` is the file to edit.

An empty `url`, a missing or wrong key (Stash answers 401) or a wrong URL path (404) makes `py_common` log an error naming `config.ini`, for example "Unable to authenticate with Stash: you need to set the API Key in 'config.ini' in the 'py_common' folder". A host that can't be reached, or any other error from Stash, fails the scrape with a Python error in the log instead.

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
