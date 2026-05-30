# stash-scrapers

Python script scrapers for [Stash](https://github.com/stashapp/stash), published as a self-hosted source index via GitHub Pages.

**Source index URL:** `https://visualhumanity.github.io/stash-scrapers/main/index.yml`

## Scrapers

| Directory | Name | Description |
|-----------|------|-------------|
| `FileMetadata` | File Metadata (ffprobe) | Reads title, URL, description, date, and performer from a video file's embedded metadata tags via ffprobe |
| `DateFromFilename` | Extract Date from Filename | Parses a scene date from the video filename, supporting a variety of formats and separators; skips and logs ambiguous cases |

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
- **stdout**: JSON object with fields to update (`{"date": "YYYY-MM-DD"}`), `{}` for no update, or `null` on a fatal error.
- Use `python` (not `python3`) to match the existing scraper manifests.
- Import logging from `py_common`: `from py_common import log` → `log.trace/debug/info/warning/error(...)`.
- Guard against missing `files` before accessing paths; print `null` and `sys.exit(0)` for non-recoverable errors.

## Build and deployment

`build_site.sh` packages each scraper into a zip and writes `index.yml`. It is run automatically by the GitHub Actions workflow (`.github/workflows/deploy.yml`) on **every push** to any branch and deploys the result to GitHub Pages under a path matching the branch name (e.g. `main/index.yml`).

Version shown in the index: the git short hash of the last commit that touched the scraper directory.

## Adding a new scraper

1. Create `scrapers/<Name>/` with a `<Name>.yml` and `<Name>.py`.
2. Follow the YAML and script conventions above.
3. Commit and push — CI builds and publishes automatically.
