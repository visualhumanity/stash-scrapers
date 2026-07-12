# Convert HTML to Markdown Scraper — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a Stash scraper, "Convert HTML to Markdown", that rewrites a scene's HTML description into Markdown (converting `<a href>` links into `[text](url)` hyperlinks) during the Identify task, leaving plain-text descriptions untouched.

**Architecture:** A `sceneByFragment` script scraper. Stash sends the scene fragment as JSON on stdin — this fragment **includes the current `details`** field (the scene description). The script detects whether `details` contains HTML; if so it converts it to Markdown with a self-contained `html.parser.HTMLParser` subclass (stdlib only) and returns `{"details": "<markdown>"}`; otherwise it returns `{}` (no change). Conversion output contains no HTML tags, so re-running is a no-op (idempotent at the process level).

**Tech Stack:** Python 3.10+ (the repo already uses 3.10 union syntax in `py_common`), stdlib `html.parser` / `re` / `json`, `py_common.log` for logging, stdlib `unittest` for tests. No third-party dependencies.

## Global Constraints

- Only files under `visualhumanity/` may be created or modified. Every path in this plan is under `D:\git\_stash\visualhumanity\stash-scrapers\`.
- Scraper manifests invoke `python` (never `python3`).
- No third-party Python dependencies — stdlib + `py_common` only. The scraper is deployed as a zip with no pip install step, so anything outside the stdlib/`py_common` will not be available at runtime.
- The scraper reads a JSON fragment from **stdin** and writes to **stdout**: a JSON object of scene fields to update (`{"details": "..."}`), `{}` for no update, or `null` on a fatal error.
- The published scraper **ID is the `.yml` basename** → `ConvertHtmlToMarkdown`. Directory, `.yml`, and `.py` all share that basename.
- `py_common` is vendored at `scrapers/community/py_common/`. Scrapers reach it by inserting `scrapers/community` onto `sys.path` (two directories up from the scraper file, then into `community`).

## Verified Facts (do not re-investigate)

- **Fragment shape** (Stash `pkg/scraper/script.go`, `sceneInput` struct): the JSON on stdin for `sceneByFragment` contains `id`, `title`, `code`, `url`, `urls`, `date`, **`details`**, `director`, and `files` (each with `path`). This scraper only needs `id` and `details`; it does **not** need `files`, so unlike `FileMetadata`/`DateFromFilename` there is no files guard.
- **Output field name** is `details` (the Stash API/GraphQL name for the "Details"/description field). `FileMetadata` maps ffprobe "description" → `scene["details"]`.
- `scrapers/community/py_common/log.py` imports only stdlib (`sys`, `re`, `traceback`, `functools`), so importing the scraper module inside a `unittest` run succeeds without any third-party package.
- `build_site.sh` zips the whole scraper directory. A `# ignore: <patterns>` comment in the `.yml` (space-separated, passed to `zip -x`) excludes files from the shipped zip. We use it to keep the test file out.

## File Structure

```
scrapers/ConvertHtmlToMarkdown/
├── ConvertHtmlToMarkdown.yml            # manifest: sceneByFragment → python ConvertHtmlToMarkdown.py
├── ConvertHtmlToMarkdown.py             # detection, HTML→Markdown converter, stdin/stdout harness
└── test_ConvertHtmlToMarkdown.py        # unittest suite (excluded from the shipped zip)

docs/superpowers/plans/2026-07-12-convert-html-to-markdown.md   # this plan
CLAUDE.md                                 # scrapers table gets one new row (Task 3)
```

Responsibilities:
- **`ConvertHtmlToMarkdown.py`** — three units: `looks_like_html(text) -> bool` (detection), `html_to_markdown(html) -> str` (conversion), and the `__main__` harness (stdin/stdout contract). Kept in one file because the scraper is packaged and run as a single script.
- **`test_ConvertHtmlToMarkdown.py`** — unit tests for detection and conversion (direct imports) plus subprocess tests for the stdin/stdout harness.

## Task Decomposition

- **Task 1** — Scaffolding, manifest, detection (`looks_like_html`), and the stdin/stdout harness with a passthrough stub converter. Independently testable: the harness's no-op cases (no details / plain text) and detection logic.
- **Task 2** — Replace the stub with the real `html.parser.HTMLParser`-based converter. Independently testable: the conversion unit tests.
- **Task 3** — End-to-end subprocess test (real HTML → Markdown through the actual script), documentation row in `CLAUDE.md`. Independently testable: the end-to-end test and a clean full test run.

---

### Task 1: Scaffolding, manifest, detection, and stdin/stdout harness

**Files:**
- Create: `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.yml`
- Create: `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py`
- Test: `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py`

**Interfaces:**
- Produces:
  - `looks_like_html(text: str) -> bool` — `True` iff `text` contains at least one HTML tag (`<` followed by a letter, `/`, or `!`). `"5 < 10"` is **not** HTML.
  - `html_to_markdown(html: str) -> str` — **stub in this task**, returns its argument unchanged. Real implementation lands in Task 2.
  - The `__main__` harness: reads a JSON fragment from stdin; prints `{}` when `details` is missing/blank or not HTML; otherwise prints `{"details": html_to_markdown(details)}` only if it differs from the input, else `{}`; prints `null` (and logs) on any exception.

- [ ] **Step 1: Create the manifest**

Create `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.yml`:

```yaml
name: Convert HTML to Markdown
# requires: py_common
# ignore: test_ConvertHtmlToMarkdown.py

sceneByFragment:
  action: script
  script:
    - python
    - ConvertHtmlToMarkdown.py
# Last Updated 2026-07-12
```

- [ ] **Step 2: Write the failing tests**

Create `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py`:

```python
import json
import os
import subprocess
import sys
import unittest

from ConvertHtmlToMarkdown import looks_like_html

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "ConvertHtmlToMarkdown.py")


def run_scraper(fragment):
    """Run the scraper as Stash would: JSON on stdin, JSON on stdout."""
    return subprocess.run(
        [sys.executable, SCRIPT],
        input=json.dumps(fragment),
        capture_output=True,
        text=True,
    )


class LooksLikeHtmlTests(unittest.TestCase):
    def test_plain_text_is_not_html(self):
        self.assertFalse(looks_like_html("Just a normal description."))

    def test_less_than_with_space_is_not_html(self):
        self.assertFalse(looks_like_html("5 < 10 and 10 > 5"))

    def test_paragraph_tag_is_html(self):
        self.assertTrue(looks_like_html("<p>Hello</p>"))

    def test_anchor_tag_is_html(self):
        self.assertTrue(looks_like_html('Visit <a href="x">x</a>'))


class HarnessTests(unittest.TestCase):
    def test_no_details_returns_empty_update(self):
        proc = run_scraper({"id": "1"})
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_blank_details_returns_empty_update(self):
        proc = run_scraper({"id": "1", "details": "   "})
        self.assertEqual(proc.stdout.strip(), "{}")

    def test_plain_text_details_returns_empty_update(self):
        proc = run_scraper({"id": "1", "details": "A plain description."})
        self.assertEqual(proc.stdout.strip(), "{}")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'ConvertHtmlToMarkdown'` (the script does not exist yet).

- [ ] **Step 4: Write the script (detection + harness + stub converter)**

Create `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py`:

```python
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown -v`
Expected: PASS — 7 tests OK. (The three `HarnessTests` exercise the real script via subprocess; with the stub converter, plain-text and missing-`details` inputs correctly yield `{}`.)

- [ ] **Step 6: Commit**

```bash
git add scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.yml scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py docs/superpowers/plans/2026-07-12-convert-html-to-markdown.md
git commit -m "Add Convert HTML to Markdown scraper scaffold and harness"
```

---

### Task 2: Real HTML→Markdown converter

**Files:**
- Modify: `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py` (replace the `html_to_markdown` stub and add the converter class + tag tables)
- Test: `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py` (add a conversion test class)

**Interfaces:**
- Consumes: `looks_like_html` and the module layout from Task 1.
- Produces: `html_to_markdown(html: str) -> str` — a real converter with these guarantees:
  - `<a href="U">T</a>` → `[T](U)`; empty `T` → `[U](U)`; missing `href` → `T` (plain text).
  - `<b>`/`<strong>` → `**…**`; `<i>`/`<em>` → `*…*`; `<code>` → `` `…` ``.
  - `<br>` / `<br/>` → single `\n`.
  - `<p>`, `<div>` → surrounding blank line; `<h1>`…`<h6>` → `#`…`######` prefix; `<blockquote>` → `> ` prefix.
  - `<ul>`/`<ol>` + `<li>` → `- item` / `1. item` (flat; nested lists are flattened, not indented).
  - HTML entities (`&amp;`, `&nbsp;`, …) decoded; unknown tags dropped but their text kept; runs of whitespace collapsed; leading/trailing whitespace and 3+ blank lines trimmed.
  - Output contains no HTML tags → `looks_like_html(html_to_markdown(x))` is `False`.

- [ ] **Step 1: Write the failing conversion tests**

Append this class to `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py` (add `html_to_markdown` to the existing import line so it reads `from ConvertHtmlToMarkdown import html_to_markdown, looks_like_html`):

```python
class HtmlToMarkdownTests(unittest.TestCase):
    def test_plain_text_passthrough(self):
        self.assertEqual(html_to_markdown("Hello world"), "Hello world")

    def test_link_becomes_markdown(self):
        self.assertEqual(
            html_to_markdown('<a href="mysite.com">Link</a>'),
            "[Link](mysite.com)",
        )

    def test_link_without_text_uses_href(self):
        self.assertEqual(
            html_to_markdown('<a href="https://x.com"></a>'),
            "[https://x.com](https://x.com)",
        )

    def test_link_without_href_keeps_text(self):
        self.assertEqual(html_to_markdown("<a>Click</a>"), "Click")

    def test_bold(self):
        self.assertEqual(html_to_markdown("<b>hi</b>"), "**hi**")
        self.assertEqual(html_to_markdown("<strong>hi</strong>"), "**hi**")

    def test_italic(self):
        self.assertEqual(html_to_markdown("<i>hi</i>"), "*hi*")
        self.assertEqual(html_to_markdown("<em>hi</em>"), "*hi*")

    def test_code(self):
        self.assertEqual(html_to_markdown("<code>x=1</code>"), "`x=1`")

    def test_br_becomes_newline(self):
        self.assertEqual(html_to_markdown("a<br>b"), "a\nb")
        self.assertEqual(html_to_markdown("a<br/>b"), "a\nb")

    def test_paragraphs_separated_by_blank_line(self):
        self.assertEqual(html_to_markdown("<p>one</p><p>two</p>"), "one\n\ntwo")

    def test_heading(self):
        self.assertEqual(html_to_markdown("<h1>Title</h1>"), "# Title")
        self.assertEqual(html_to_markdown("<h3>Sub</h3>"), "### Sub")

    def test_unordered_list(self):
        self.assertEqual(
            html_to_markdown("<ul><li>a</li><li>b</li></ul>"),
            "- a\n- b",
        )

    def test_ordered_list(self):
        self.assertEqual(
            html_to_markdown("<ol><li>a</li><li>b</li></ol>"),
            "1. a\n2. b",
        )

    def test_unknown_tags_stripped_content_kept(self):
        self.assertEqual(html_to_markdown('<span class="x">kept</span>'), "kept")

    def test_entities_decoded(self):
        self.assertEqual(html_to_markdown("Tom &amp; Jerry"), "Tom & Jerry")

    def test_whitespace_collapsed(self):
        self.assertEqual(
            html_to_markdown("<p>  lots   of\n\n  space </p>"),
            "lots of space",
        )

    def test_nested_formatting_in_link(self):
        self.assertEqual(html_to_markdown('<a href="u"><b>x</b></a>'), "[**x**](u)")

    def test_real_world_example(self):
        html = (
            '<p>Check out my <a href="https://example.com">website</a>!</p>'
            "<p>Filmed in <b>4K</b>.</p>"
        )
        self.assertEqual(
            html_to_markdown(html),
            "Check out my [website](https://example.com)!\n\nFilmed in **4K**.",
        )

    def test_output_has_no_html_tags(self):
        once = html_to_markdown('<p>Hi <a href="u">l</a></p>')
        self.assertFalse(looks_like_html(once))
```

- [ ] **Step 2: Run the conversion tests to verify they fail**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown.HtmlToMarkdownTests -v`
Expected: FAIL — e.g. `test_link_becomes_markdown` fails with `AssertionError: '<a href="mysite.com">Link</a>' != '[Link](mysite.com)'` (the stub returns input unchanged).

- [ ] **Step 3: Replace the stub with the real converter**

In `scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py`:

(a) Add `from html.parser import HTMLParser` to the top imports (below `import sys`).

(b) Add these tag tables directly beneath the existing `_HTML_TAG_RE` definition:

```python
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
```

(c) Replace the entire stub `html_to_markdown` function with the converter class and the real function:

```python
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
```

- [ ] **Step 4: Run the full test suite to verify it passes**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown -v`
Expected: PASS — all tests OK (7 from Task 1 + 18 conversion tests).

- [ ] **Step 5: Commit**

```bash
git add scrapers/ConvertHtmlToMarkdown/ConvertHtmlToMarkdown.py scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py
git commit -m "Implement HTML to Markdown conversion"
```

---

### Task 3: End-to-end verification and documentation

**Files:**
- Test: `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py` (add one end-to-end subprocess test)
- Modify: `CLAUDE.md` (add a row to the Scrapers table)

**Interfaces:**
- Consumes: the complete `ConvertHtmlToMarkdown.py` from Tasks 1–2 and the `run_scraper` helper from Task 1's test file.
- Produces: proof that a real HTML `details` fragment is converted end-to-end through the actual script, and a documentation entry.

- [ ] **Step 1: Write the failing end-to-end test**

Add this method to the existing `HarnessTests` class in `scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py`:

```python
    def test_html_details_converted_end_to_end(self):
        proc = run_scraper(
            {"id": "42", "details": '<p>See <a href="https://x.com">here</a>.</p>'}
        )
        self.assertEqual(
            json.loads(proc.stdout),
            {"details": "See [here](https://x.com)."},
        )
```

- [ ] **Step 2: Run the end-to-end test to verify it passes**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown.HarnessTests.test_html_details_converted_end_to_end -v`
Expected: PASS — the real script converts the HTML `details` and prints `{"details": "See [here](https://x.com)."}`.

(If Task 2 were incomplete this would FAIL because the stub echoes the HTML back and `main` would emit `{}`; it passes now that the real converter is in place.)

- [ ] **Step 3: Add the scraper to the documentation table**

In `CLAUDE.md`, find the Scrapers table:

```markdown
| `FileMetadata` | File Metadata (ffprobe) | Reads title, URL, description, date, and performer from a video file's embedded metadata tags via ffprobe |
| `DateFromFilename` | Extract Date from Filename | Parses a scene date from the video filename, supporting a variety of formats and separators; skips and logs ambiguous cases |
```

Add this row immediately after the `DateFromFilename` row:

```markdown
| `ConvertHtmlToMarkdown` | Convert HTML to Markdown | Converts an HTML scene description (e.g. one extracted from embedded video metadata) into Markdown, turning links into `[text](url)` hyperlinks; leaves plain-text descriptions untouched |
```

- [ ] **Step 4: Run the complete test suite one final time**

Run: `cd scrapers/ConvertHtmlToMarkdown && python -m unittest test_ConvertHtmlToMarkdown -v`
Expected: PASS — all tests OK (8 harness/detection + 18 conversion).

- [ ] **Step 5: Commit**

```bash
git add scrapers/ConvertHtmlToMarkdown/test_ConvertHtmlToMarkdown.py CLAUDE.md
git commit -m "Add end-to-end test and document Convert HTML to Markdown scraper"
```

---

## Self-Review

**Spec coverage:**
- "Scraper called 'Convert HTML to Markdown'" → manifest `name: Convert HTML to Markdown` (Task 1, Step 1).
- "Converts HTML within the scene description to Markdown" → `html_to_markdown` + harness reading/writing `details` (Tasks 1–2).
- "URLs converted into Markdown hyperlinks, e.g. `[Link](mysite.com)`" → `test_link_becomes_markdown` asserts exactly `[Link](mysite.com)` (Task 2).
- "Plain text renders perfectly / only act on HTML" → `looks_like_html` gate; plain text yields `{}` (Task 1 harness tests).
- "Validating the markdown-render plugin is installed is out of scope" → no plugin checks anywhere; the scraper only writes Markdown into `details`.

**Placeholder scan:** No TBD/TODO/"add error handling"/"similar to Task N". The `html_to_markdown` stub in Task 1 is an explicit, intentional passthrough that Task 2 replaces (called out in both tasks), not a placeholder.

**Type consistency:** `looks_like_html(str) -> bool`, `html_to_markdown(str) -> str`, `run_scraper(dict) -> CompletedProcess`, and helper names (`_emit`, `_li_prefix`, `get_markdown`, `_INLINE_WRAP`, `_HEADINGS`, `_HTML_TAG_RE`) are used identically across tasks. The test import line is `from ConvertHtmlToMarkdown import html_to_markdown, looks_like_html` after Task 2's Step 1 amends it.
