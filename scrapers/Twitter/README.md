# VH - Twitter

Scrapes a performer from a Twitter/X profile through the X API, by profile URL or by handle.

## Supports

- **Performer** (by URL, by name): name, urls. By URL also fills details, image and twitter.

Profile URLs can be on `twitter.com` or `x.com`.

## Field notes

- **name**: the account's display name, not its handle.
- **urls** and **twitter**: `https://twitter.com/<handle>`, with the handle as the API spells it, even for an `x.com` URL.
- **details**: the profile's bio.
- **image**: the profile picture at 400x400.

## Searching by name

Scrape by name looks up the exact handle typed, with or without a leading `@` (`@example_user` or `example_user`). It is not a search: it gives one result or none, and a display name with spaces gives none. The result has only a name and URL; to fill the rest, scrape the performer again by its URL.

## Configuration

- Set the environment variable `TWITTER_BEARER_TOKEN` to an X API bearer token in the environment Stash runs in (for Docker, the container's environment). Without it, every scrape logs an error and gives no result. The token's X API access tier must allow user lookup by username.

## Known limitations

- Only the first part of the URL path is read as the handle, so a URL such as `https://x.com/i/status/1` looks up the handle `i`.
- An unknown handle, an invalid or expired token, an API error or no answer in 10 seconds logs a message and gives no result.

## Development

- One call to the X API v2 endpoint `users/by/username/<handle>`, asking for `name`, `description` and `profile_image_url`.
- No tests.
