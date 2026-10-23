# stash-scrapers

Python script scrapers for [Stash](https://github.com/stashapp/stash), published as a self-hosted source index via GitHub Pages.

**Source index URLs:** `https://visualhumanity.github.io/stash-scrapers/main/index.yml` (releases) and `https://visualhumanity.github.io/stash-scrapers/develop/index.yml` (pre-release builds from `develop`, for testing on a test Stash instance)

## Scrapers

| Directory | Name | Description |
|-----------|------|-------------|
| `FileMetadata` | VH - File Metadata (ffprobe) | Reads title, URL, description, date, and performer from a video file's embedded metadata tags via ffprobe |
| `DateFromFilename` | VH - Extract Date from Filename | Parses a scene date from the video file's name (never its folders): numeric dates, `YY.MM.DD` scene releases, English, French and Spanish month names (`Feb 16, 2025`, `16 de febrero de 2025`, `16Feb2025`), partial dates (`Feb 2025`, `2025-02`, `(2019)`) and, as a last resort, Unix timestamps at the start or end of the name (container `TZ`); the most precise date wins, then the leftmost; skips and logs ambiguous cases |
| `ConvertHtmlToMarkdown` | VH - Convert HTML to Markdown | Converts an HTML scene description (e.g. one extracted from embedded video metadata) into Markdown, turning links into `[text](url)` hyperlinks; leaves plain-text descriptions untouched |
| `GalleryDlReddit` | VH - Reddit (Gallery-DL) | Reads the gallery-dl `<media file>.json` Reddit metadata file next to a scene or image and fills title, date (UTC), URL (permalink), code (post ID), details (post text), performer (`u_<author>` with profile URL), studio (`r/<subreddit>`, parent `Reddit`) and tag (flair); without a usable one (missing, RedGIFs) falls back to the file name (`<title> - <YYYY-MM-DD> - u_<author>[ - <n>]`) for title, date and performer (profile URL for `u_<author>`) plus studio from the `r_<subreddit>` folder. Images use the file paths in the scrape input when Stash sends them, otherwise a GraphQL lookup (`py_common/config.ini`); see its README |
| `GalleryDlTwitter` | VH - Gallery-DL - Twitter | Reads the gallery-dl `<media file>.json` sidecar next to a Twitter scene or image and fills title (first caption line, ` [i]` for multi-media tweets), details, date (container `TZ`), code (tweet ID), URL, performer and studio (poster handle) and tags (hashtags); skips avatar/background sidecars. Images need an API key in `py_common/config.ini`; see its README |
| `OFScraperUserData` | VH - OF-Scraper - User Data | Reads OF-Scraper's per-account `user_data.db` (read-only) to fill title (inferred from the description: first usable line, cut at emoji or sentence ends, filler removed), date (container `TZ`), studio and performer (model folder), mentioned accounts as extra performers, URL (posts only) and description converted to Markdown via the `ConvertHtmlToMarkdown` module (required package); scene by fragment only |
| `vhTitleFromPerformers` | VH - Title From Performers | Sets the scene title from the scene's saved performers (`A & B`, `A, B, & C`), ordered by gender group (male and unset first), rating tier (3 stars and up, unrated, below 3 stars), rating, then name; reads ratings and genders through the Stash API (`py_common/config.ini`); no title for 0 or 1 performers; see its README |

## Directory structure

```
scrapers/
└── <ScraperName>/
    ├── <ScraperName>.yml   # scraper manifest
    └── <ScraperName>.py    # Python script
```

The scraper ID (used in the published index and zip filename) is derived from the `.yml` filename.

## YAML manifest

```yaml
name: Human-readable Name
# requires: py_common          # optional: comma-separated dependency IDs

sceneByFragment:               # action exposed in the Stash Identify task
  action: script
  script:
    - python                   # use "python", not "python3"
    - ScraperName.py
# Last Updated YYYY-MM-DD
```

- `# requires:` is a comment convention parsed by the build script; it populates `requires:` in the published index.
- `# ignore:` (another supported comment) lists files to exclude from the zip.
- Other supported actions besides `sceneByFragment`: `sceneByURL`, `sceneByName`, `performerByURL`, etc.

## Python script conventions

- **stdin**: JSON fragment from Stash — always contains `id`; `files` (list with `path`) is present for `sceneByFragment`.
- **stdout**: JSON object with fields to update (`{"date": "YYYY-MM-DD"}`), `{}` for no update, or `null` on a fatal error. Dates may also be partial, `YYYY-MM` or `YYYY`: Stash (0.31.1 checked) stores them with month or year precision.
- Use `python` (not `python3`) to match the existing scraper manifests.
- Import logging from `py_common`: `from py_common import log` → `log.trace/debug/info/warning/error(...)`.
- Before any `py_common` import, add `<scrapers>/community` to `sys.path` (copy the block at the top of `DateFromFilename.py`). Stash's default Community source installs `py_common` into `scrapers/community/`, but only puts `scrapers/` on `PYTHONPATH`, so a bare import fails unless another source happens to install `py_common` at the top level.
- Guard against missing `files` before accessing paths; print `null` and `sys.exit(0)` for non-recoverable errors.

## Build and deployment

`build_site.sh` packages each scraper into a zip and writes `index.yml`. It is run automatically by the GitHub Actions workflow (`.github/workflows/deploy.yml`), which has a `build` and a `deploy` job.

- **Triggers:** PRs into `main` or `develop`, pushes to those branches, and manual runs. PRs and pushes only start the workflow when they touch `scrapers/**`, `build_site.sh` or `.github/workflows/**`.
- **PRs:** `build` runs against the PR's feature branch (its head commit). Nothing is deployed.
- **Pushes and manual runs:** `build` checks out both `main` and `develop` and builds them into `_site/main` and `_site/develop`, then `deploy` publishes both. A Pages artifact deploy replaces the whole site, so both branches are always rebuilt together.
- **Deploy:** runs only from `main` or `develop`. The `github-pages` environment allows deploys from those two branches only.
- **Queueing:** pushes and manual runs on `main` or `develop` share one concurrency group with `queue: max`, so they run one at a time in order and waiting runs are not cancelled. PR runs and manual runs on other branches never wait on it.

Version shown in the index: the git short hash of the last commit that touched the scraper directory.

## Adding a new scraper

1. Create `scrapers/<Name>/` with a `<Name>.yml` and `<Name>.py`.
2. Follow the YAML and script conventions above.
3. Commit and push — CI builds and publishes automatically.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
