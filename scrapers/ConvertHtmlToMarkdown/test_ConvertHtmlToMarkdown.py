import json
import os
import subprocess
import sys
import unittest

from ConvertHtmlToMarkdown import html_to_markdown, looks_like_html

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


if __name__ == "__main__":
    unittest.main()
