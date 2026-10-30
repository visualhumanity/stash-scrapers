# VH - Convert HTML to Markdown

Converts a scene's HTML description into Markdown, keeping links as `[text](url)`. A description with no HTML tags is left unchanged.

## Supports

- **Scene** (by fragment): details

## Conversion

The scene's current description is read and rewritten in place. It counts as HTML when it holds at least one tag: `<` followed by a letter, `/` or `!`, so `5 < 10` is plain text.

- `<a href="https://example.com/">Example</a>` becomes `[Example](https://example.com/)`. A link with no text uses its URL as text; a link with no `href` keeps only its text.
- `<b>` and `<strong>` become `**bold**`, `<i>` and `<em>` become `*italic*`, `<code>` becomes `` `code` ``.
- `<h1>` to `<h6>` become `#` to `######` headings.
- `<ul>` items become `- ` lines, `<ol>` items become `1. `, `2. ` lines.
- `<blockquote>` becomes a `> ` line.
- `<p>` and `<div>` become paragraphs separated by a blank line; `<br>` becomes a newline.
- Other tags are removed and their text kept. Entities such as `&amp;` are decoded, and runs of spaces and line breaks inside text collapse to one space.

## Known limitations

- Nested lists are flattened to one level.
- Images are dropped, including their `alt` text.
- Tables lose their structure: cell text runs together.
- `<pre>` blocks lose their line breaks and indentation.
- The text inside `<script>` and `<style>` tags is kept as plain text.
- A blockquote holding paragraphs loses its quoting: the `>` ends up on a line of its own.
- Spaces just inside a bold or italic tag stay inside the markers (`<b> bold </b>` gives `** bold **`), which Markdown does not render as bold.
- Markdown characters already in the text, such as `*` or `_`, are not escaped.

## Development

- `html_to_markdown()` streams the description through the standard library's `HTMLParser`; `looks_like_html()` decides whether to convert.
- `OFScraperUserData` imports both functions from this folder to convert its descriptions, so a change here changes its output too.
- Tests: `python3 -B -m unittest -v` from this folder. They cover the converter directly and run the script as a subprocess for the input and output checks; they never contact Stash.
