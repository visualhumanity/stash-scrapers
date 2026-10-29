# Every scraper has a README with a shared structure

Every scraper has a `README.md` in its own folder. A PR that adds a scraper or changes what it does adds or updates that README in the same PR. Where information lives (root README, folder README or `CLAUDE.md`) is set by [ADR 0001](0001-root-readme-role.md); this ADR covers what a folder README holds and in what order. A unit test fails when a scraper folder has no `README.md`.

The READMEs follow one structure, shared with plugin READMEs in stash-plugins, so a reader finds the same thing in the same place in either repo. User-facing sections come first, maintainer material last. The anchor headings, in order:

- H1: the scraper's `name:` from its `.yml`.
- A description of 1-3 sentences.
- A `Requires:` line, only for dependencies beyond what every scraper gets. Link each one as specifically as possible: a relative link to its folder when it is in this repo, otherwise its folder in the external repo, otherwise the repo or project page.
- `## Supports`: one bullet per entity type the scraper handles, with the actions and the fields it fills.
- Free sections specific to the scraper, such as a title format or how files are matched.
- `## Field notes`, optional.
- `## Configuration`, only when the scraper has something to configure.
- `## Known limitations`, optional.
- `## Development`: tests and internals, kept short.

Specific to scrapers:

- "What every scraper gets" is `py_common`: every scraper here requires it, and the root README says how it is installed.
- Free sections go only between Supports and Field notes.
- Each Supports bullet is the entity type in bold, then the actions in parentheses in plain words ("by URL", "by fragment", "by name"), then the fields, for example `**Scene** (by fragment): title, date, urls, performers`. Types and actions match the `.yml` action keys exactly: `sceneByFragment` becomes `**Scene** (by fragment)`. A "Not filled" line may list notable gaps.
- Field notes cover non-obvious fields only, such as a title capped at a length or a date converted between time zones. Obvious mappings are not documented. Field, source and rule tables are cut down to the notes worth keeping.
- The shared `py_common` `config.ini` steps live in the root README's [Install section](../../README.md#configure-py_common). A scraper that needs them says so in one line under Configuration and links there.

Spelling is US, as in Stash. Field names, keys, action names and UI labels are quoted exactly as Stash or the code spells them.

When restructuring an existing README, move and trim its content rather than rewriting it. A "Behavior" section or log-level table splits by audience: user-visible rules go to Field notes or a free section, failure cases a user can hit to Known limitations, internals and logging detail to Development.

All examples are synthetic (`Example Scene`, `/data/example/video.mp4`): no real titles, names, usernames, hosts or paths outside the repo.

This is guidance, not a template. Agents may add free sections, adjust wording and trim content without amending this ADR. Only a change to whether READMEs exist, where they live, when they are kept current, or the anchor headings needs a new ADR.

## Considered options

- No written rule: six scrapers had no README, the other four each had their own headings, and three repeated the `py_common` `config.ini` steps in different words.
- A strict template with a heading linter: turns guidance into boilerplate, and scrapers with no configuration or limitations would carry empty headings.
- A ✅/❌ matrix of entity types and actions: less concise than one bullet per supported type.
- Generating Supports from the `.yml` action keys: with ten scrapers, hand-written lists checked at review are simpler.
