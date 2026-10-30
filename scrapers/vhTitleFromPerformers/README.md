# VH - Title From Performers

Suggests a scene title built from the scene's performers, for example `Example Performer A, Example Performer B, & Example Performer C`. It works from the scene edit tab ("Scrape with") and from the Identify task.

## Supports

- **Scene** (by fragment): title

## Which performers

Only the performers **saved** on the scene are used. Performers added in the edit tab but not saved yet are not seen, so save first, then scrape. In an Identify run, performers that another source adds to the same scene in that run are not seen either.

## Title format

- Names only; a performer's disambiguation is not included.
- 2 performers: `A & B`
- 3 or more: `A, B, & C`, `A, B, C, & D` (always `&`, never "and", always the Oxford comma)
- Names are copied exactly as stored in Stash: accents, Greek and other scripts, case, digits, symbols and emoji are kept. A name that itself contains `&` or `,` is used as is.
- There is no length limit; a scene with many performers gets a long title.

## Order

Performers are sorted by each rule in turn; a later rule only breaks ties left by the ones before it.

1. **Gender:** male and no gender set first; then female, transgender male, transgender female, intersex and non-binary.
2. **Rating tier**, within each gender group:
   1. rated 3 stars or more (`rating100` 60 or higher)
   2. unrated
   3. rated below 3 stars
3. **Rating**, highest first, within a tier.
4. **Name**, A to Z, ignoring case.
5. **Exact name**, so names that differ only in case (`Alex`, `alex`) always come out in the same order.

Names are compared character by character with no other adjustment, so accented capitals (`Á`, `Ñ`) sort after `Z`, `10` sorts before `9`, and names starting with a symbol or emoji sort first or last.

## Using it with Identify

Add **VH - Title From Performers** as a source. With Identify's default field strategy (Merge), a title is only set on scenes that have none. To replace existing titles, set the **Title** field strategy for this source to **Overwrite**. Performers must already be saved on the scenes; put this source after any source that adds performers, and run Identify again once those are saved.

## Configuration

- Needs `py_common` set up as in the root README's [Install section](../../README.md#configure-py_common): Stash does not give a scraper the scene's performer ratings or genders, so the scraper asks Stash's GraphQL API for them.

## Known limitations

- A scene with 0 or 1 performers gets no title, and its existing title is left alone. An Info line is logged.
- When the Stash API can't be reached, the URL or API key in `config.ini` is wrong, or the scene is not found, the scrape fails with an error in the log. The title is left alone.

## Development

- Tests: `python3 -B -m unittest -v` from this folder. They use made-up performers and a stand-in for the Stash API; they never contact Stash.
- The 3-star cutoff (`RATING_CUTOFF`) and the genders listed last (`LAST_GENDERS`) are constants at the top of `vhTitleFromPerformers.py`.
