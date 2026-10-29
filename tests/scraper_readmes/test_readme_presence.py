import os
import unittest

SCRAPERS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "scrapers")

# Not scrapers: "community" is the vendored py_common; "automatic_dependencies" is where
# py_common's deps.py installs packages when a scraper's tests run locally
EXCLUDED = {"community", "automatic_dependencies"}


class ReadmePresenceTest(unittest.TestCase):
    # ADR 0002: every scraper has a README.md in its own folder.
    def test_every_scraper_folder_has_readme(self):
        # Skip caches and hidden folders (__pycache__, .pytest_cache), which aren't scrapers
        folders = sorted(
            name
            for name in os.listdir(SCRAPERS_DIR)
            if os.path.isdir(os.path.join(SCRAPERS_DIR, name))
            and not name.startswith((".", "__"))
            and name not in EXCLUDED
        )
        self.assertTrue(folders, "no scraper folders found")
        missing = [f for f in folders if not os.path.isfile(os.path.join(SCRAPERS_DIR, f, "README.md"))]
        self.assertEqual(missing, [], f"scraper folders without README.md: {', '.join(missing)}")
