import json
import os
import re
import sys
from html.parser import HTMLParser

# py_common is vendored at scrapers/community/py_common/; this scraper lives at
# scrapers/<vendor>/ConvertHtmlToMarkdown/ — go up two levels then into community/
sys.path.insert(
    0,
    os.path.join(
        os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"
    ),
)

try:
    from py_common import log
except ModuleNotFoundError:
    print(
        "You need to install py_common from the community scraper package.",
        file=sys.stderr,
    )
    sys.exit(1)


# Matches an HTML tag: '<' followed by a letter, '/', or '!' (so "5 < 10" is not
# treated as markup) up to the next '>'.
_HTML_TAG_RE = re.compile(r"<[a-zA-Z/!][^>]*>")

# Inline tags whose content is wrapped in a symmetric Markdown marker.
_INLINE_WRAP = {
    "b": "**",
    "strong": "**",
    "i": "*",
    "em": "*",
    "code": "`",
}

# Heading tags -> Markdown ATX prefix.
_HEADINGS = {f"h{n}": "#" * n for n in range(1, 7)}


def looks_like_html(text: str) -> bool:
    """Return True if the text contains at least one HTML tag."""
    return bool(_HTML_TAG_RE.search(text))


class _MarkdownConverter(HTMLParser):
    """Streaming HTML -> Markdown converter built on the stdlib HTMLParser.

    Unknown tags are dropped but their text content is preserved. Nested lists
    are flattened to a single level.
    """

    def __init__(self):
        # convert_charrefs=True decodes entities (&amp; &nbsp; ...) into the text
        # handed to handle_data, so we don't handle character references here.
        super().__init__(convert_charrefs=True)
        self._parts: list[str] = []
        self._list_stack: list[dict] = []
        self._link_href = None
        self._link_start = None

    def _emit(self, text: str) -> None:
        self._parts.append(text)

    def _li_prefix(self) -> str:
        top = self._list_stack[-1] if self._list_stack else None
        if top and top["ordered"]:
            top["index"] += 1
            return f"{top['index']}. "
        return "- "

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag == "br":
            self._emit("\n")
        elif tag == "a":
            self._link_href = dict(attrs).get("href")
            self._link_start = len(self._parts)
        elif tag in _INLINE_WRAP:
            self._emit(_INLINE_WRAP[tag])
        elif tag in _HEADINGS:
            self._emit("\n\n" + _HEADINGS[tag] + " ")
        elif tag in ("ul", "ol"):
            self._list_stack.append({"ordered": tag == "ol", "index": 0})
            self._emit("\n")
        elif tag == "li":
            self._emit("\n" + self._li_prefix())
        elif tag == "blockquote":
            self._emit("\n\n> ")
        elif tag in ("p", "div"):
            self._emit("\n\n")
        # any other tag: strip it, keep its text content

    def handle_startendtag(self, tag, attrs):
        if tag.lower() == "br":
            self._emit("\n")
        else:
            self.handle_starttag(tag, attrs)
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "a":
            if self._link_start is not None:
                text = "".join(self._parts[self._link_start:]).strip()
                del self._parts[self._link_start:]
            else:
                text = ""
            href = self._link_href
            self._link_href = None
            self._link_start = None
            if href:
                self._emit(f"[{text or href}]({href})")
            elif text:
                self._emit(text)
        elif tag in _INLINE_WRAP:
            self._emit(_INLINE_WRAP[tag])
        elif tag in _HEADINGS:
            self._emit("\n\n")
        elif tag in ("ul", "ol"):
            if self._list_stack:
                self._list_stack.pop()
            self._emit("\n")
        elif tag in ("p", "div", "blockquote"):
            self._emit("\n\n")

    def handle_data(self, data):
        if not data:
            return
        self._emit(re.sub(r"\s+", " ", data))

    def get_markdown(self) -> str:
        text = "".join(self._parts)
        text = re.sub(r"[ \t]+", " ", text)      # collapse horizontal whitespace
        text = re.sub(r" *\n *", "\n", text)     # trim whitespace around newlines
        text = re.sub(r"\n{3,}", "\n\n", text)   # cap consecutive blank lines
        return text.strip()


def html_to_markdown(html: str) -> str:
    """Convert an HTML string to Markdown."""
    parser = _MarkdownConverter()
    parser.feed(html)
    parser.close()
    return parser.get_markdown()


if __name__ == "__main__":
    try:
        fragment = json.loads(sys.stdin.read())
        scene_id = fragment.get("id", "unknown")
        details = fragment.get("details") or ""

        if not details.strip():
            log.debug(f"Scene {scene_id}: no description to convert")
            print(json.dumps({}))
            sys.exit(0)

        if not looks_like_html(details):
            log.debug(f"Scene {scene_id}: description is not HTML; leaving unchanged")
            print(json.dumps({}))
            sys.exit(0)

        markdown = html_to_markdown(details)
        if markdown and markdown != details:
            log.info(f"Scene {scene_id}: converted HTML description to Markdown")
            print(json.dumps({"details": markdown}))
        else:
            print(json.dumps({}))
    except Exception as exc:
        log.error(f"Failed to convert description: {exc}")
        print("null")
        sys.exit(0)
