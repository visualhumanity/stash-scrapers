import json
import os
import re
import sys

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


def looks_like_html(text: str) -> bool:
    """Return True if the text contains at least one HTML tag."""
    return bool(_HTML_TAG_RE.search(text))


def html_to_markdown(html: str) -> str:
    """Convert an HTML string to Markdown.

    Stub implementation — replaced with the real converter in Task 2.
    """
    return html


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
