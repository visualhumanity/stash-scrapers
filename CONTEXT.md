# Stash Scrapers

Scrapers for Stash, published from this repo to two source indexes: one for users and one for testing.

## Language

### Publishing

**Source index**:
The `index.yml` file that Stash reads to list the scrapers it can install from a source, together with the zip files it points to.
_Avoid_: feed, repo index

**Production index**:
The source index built from `main`. It holds released scrapers, which users install from.
_Avoid_: release index, stable index, main index

**Develop index**:
The source index built from `develop`. It holds pre-release builds, which are tested on a test Stash instance.
_Avoid_: pre-release index, dev index, staging index

**Release PR**:
A pull request from `develop` into `main`.
_Avoid_: deploy PR, merge-up

**Promotion**:
Moving changes from `develop` to `main` through a release PR.
_Avoid_: deploy, publish

### Versioning

**Scraper version**:
The git short hash of the last commit that touched a scraper's folder, as shown in a source index. Scrapers have no hand-set version.
_Avoid_: semver, release number
