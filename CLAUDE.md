# stash-scrapers

Python script scrapers for [Stash](https://github.com/stashapp/stash), published as a self-hosted source index via GitHub Pages.

**Source index URLs:** `https://visualhumanity.github.io/stash-scrapers/main/index.yml` (releases) and `https://visualhumanity.github.io/stash-scrapers/develop/index.yml` (pre-release builds from `develop`, for testing on a test Stash instance)

## Scrapers

The root [`README.md`](README.md) is the index of the scrapers in this repo: name and a short description. Each scraper's own `README.md` holds the detail (setup, fields, behaviour). Read those rather than expecting a list here. See `docs/adr/0001-root-readme-role.md`.

Every scraper folder has a `README.md` following the shared structure in `docs/adr/0002-scraper-readme-structure.md`.

Keep the README table current: a PR that adds, removes or renames a scraper, or changes what it does, updates the table in the same PR. The table has no version column; see the ADR.

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

1. Create `scrapers/<Name>/` with a `<Name>.yml`, a `<Name>.py` and a `README.md`.
2. Follow the YAML and script conventions above.
3. Add a row for it to the root `README.md` scrapers table.
4. Open a PR into `develop`. After merge, CI publishes it to the develop index; a release PR into `main` publishes it to the production index.

## Agent skills

### Issue tracker

Issues live in GitHub Issues (`gh` CLI). See `docs/agents/issue-tracker.md`.

### Triage labels

Default five-label vocabulary. See `docs/agents/triage-labels.md`.

### Domain docs

Single-context: root `CONTEXT.md` + `docs/adr/`. See `docs/agents/domain.md`.
