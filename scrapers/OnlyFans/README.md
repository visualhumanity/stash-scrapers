# VH - OnlyFans

Scrapes a performer or a studio from an OnlyFans profile URL, such as `https://onlyfans.com/example_creator`.

## Supports

- **Performer** (by URL): name, details, image, urls
- **Studio** (by URL): name, details, image, urls

## Field notes

- **image**: the performer gets the profile picture. The studio gets the profile header image, or the profile picture when there is no header.
- **urls**: `https://onlyfans.com/<username>`, with anything after the username in the scraped URL dropped.

## Configuration

- **Cookies (optional):** without them only public profile data is read, and the studio's header image can be missing. To scrape with a logged-in session, export your OnlyFans browser cookies in Netscape `cookies.txt` format to a file named `OnlyFans.cookies` in this scraper's folder, next to `OnlyFans.py`. The file holds your login session: keep it private.
- **Stash 0.30.0 or older:** studio scrapes ask Stash for its version through `py_common`, to fill the single `url` field those versions use. Set up `py_common` as in the root README's [Install section](../../README.md#configure-py_common). On newer Stash this is not needed.

## Known limitations

- Only the first part of the URL path is read as the username: `https://onlyfans.com/example_creator/media` scrapes `example_creator`. Site pages such as `onlyfans.com/home` or `onlyfans.com/search` give no result.
- A profile that cannot be fetched (an HTTP error, a block or no answer in 15 seconds) logs an error and gives no result.
- When the version lookup fails (`py_common` not set up, a wrong API key, Stash unreachable), a studio scrape fills `urls` as for newer Stash. A `config.ini` problem also logs a `py_common` error.
- An unreadable cookies file is skipped with a warning, and the scrape goes on without cookies.

## Development

- No tests.
- The profile is read from the page's embedded Next.js data (`__NEXT_DATA__`), falling back to its OpenGraph `og:` tags, which have no header image.
- `py_common` installs `requests` and `lxml` on first run if they are missing.
