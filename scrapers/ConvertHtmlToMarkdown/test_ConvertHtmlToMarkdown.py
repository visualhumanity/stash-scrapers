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
