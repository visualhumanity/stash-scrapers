# All sample data in this file is made up
import json
import os
import subprocess
import sys
import tempfile
import unittest

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "GalleryDlReddit.py")

ERROR = "\x01e\x02"
WARNING = "\x01w\x02"

# Runs the scraper as __main__ with py_common.graphql replaced through sys.modules.
# The fake returns the JSON in FAKE_GRAPHQL_RESULT (or raises when FAKE_GRAPHQL_RAISE
# is set) and appends each call's variables to the file named by FAKE_GRAPHQL_CALLS.
WRAPPER = r"""
import json, os, runpy, sys, types

def callGraphQL(query, variables=None):
    with open(os.environ["FAKE_GRAPHQL_CALLS"], "a", encoding="utf-8") as f:
        f.write(json.dumps(variables) + "\n")
    if os.environ.get("FAKE_GRAPHQL_RAISE"):
        raise ConnectionError("connection refused")
    return json.loads(os.environ.get("FAKE_GRAPHQL_RESULT", "null"))

fake = types.ModuleType("py_common.graphql")
fake.callGraphQL = callGraphQL
sys.modules["py_common.graphql"] = fake

script = sys.argv[1]
sys.argv = sys.argv[1:]
runpy.run_path(script, run_name="__main__")
"""


class ScraperTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = tmp.name
        self.calls_file = os.path.join(self.dir, "graphql_calls.jsonl")

    def path(self, name, folder="r_ExampleSub"):
        return os.path.join(self.dir, folder, name)

    def write_metadata(self, media_path, meta, raw=None):
        """Write gallery-dl's "<media file name>.json" next to the media path."""
        os.makedirs(os.path.dirname(media_path), exist_ok=True)
        with open(media_path + ".json", "w", encoding="utf-8") as f:
            if raw is not None:
                f.write(raw)
            else:
                # Matches gallery-dl's own formatting, which keeps non-ASCII characters raw
                json.dump(meta, f, indent=4, ensure_ascii=False)
        return media_path

    def run_scraper(self, operation, fragment, graphql_result=None, graphql_raises=False):
        """Run the scraper as Stash would: JSON on stdin, JSON on stdout."""
        env = dict(os.environ)
        env["FAKE_GRAPHQL_CALLS"] = self.calls_file
        env["FAKE_GRAPHQL_RESULT"] = json.dumps(graphql_result)
        if graphql_raises:
            env["FAKE_GRAPHQL_RAISE"] = "1"
        return subprocess.run(
            [sys.executable, "-B", "-c", WRAPPER, SCRIPT, operation],
            input=json.dumps(fragment),
            capture_output=True,
            text=True,
            env=env,
        )

    def graphql_calls(self):
        if not os.path.exists(self.calls_file):
            return []
        with open(self.calls_file, encoding="utf-8") as f:
            return [json.loads(line) for line in f]

    def output(self, proc):
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return json.loads(proc.stdout)


EXAMPLE_STUDIO = {
    "name": "r/ExampleSub",
    "urls": ["https://www.reddit.com/r/ExampleSub"],
    "parent": {"name": "Reddit"},
}

# Filename fallback for a file in an r_ExampleSub folder
EXPECTED = {
    "title": "Example Post",
    "date": "2001-02-03",
    "performers": [{"name": "u_example_user", "urls": ["https://www.reddit.com/user/example_user"]}],
    "studio": EXAMPLE_STUDIO,
}

# Filename fallback outside an r_<subreddit> folder: the output from before metadata files
EXPECTED_NO_STUDIO = {k: v for k, v in EXPECTED.items() if k != "studio"}

FILE_NAME = "Example Post - 2001-02-03 - u_example_user.mp4"


def reddit_metadata(**overrides):
    """A made-up gallery-dl Reddit metadata file (a subset of the real keys)."""
    meta = {
        "category": "reddit",
        "subcategory": "submission",
        "id": "abc123",
        "title": "Example Post: the full title?",
        "author": "example_user",
        "subreddit": "ExampleSub",
        "permalink": "/r/ExampleSub/comments/abc123/example_post/",
        "url": "https://i.example.com/example.jpg",
        "selftext": "Example post text.\n\nSecond paragraph.",
        "link_flair_text": "2",
        "over_18": True,
        "created_utc": 981173696.0,
        "date": "2001-02-03 04:14:56",
        "num": 0,
        "filename": "example",
        "extension": "mp4",
    }
    meta.update(overrides)
    return meta


EXPECTED_FROM_METADATA = {
    "title": "Example Post: the full title?",
    "date": "2001-02-03",
    "urls": ["https://www.reddit.com/r/ExampleSub/comments/abc123/example_post/"],
    "code": "abc123",
    "details": "Example post text.\n\nSecond paragraph.",
    "performers": [{"name": "u_example_user", "urls": ["https://www.reddit.com/user/example_user"]}],
    "studio": EXAMPLE_STUDIO,
    "tags": [{"name": "2"}],
}


class SceneTests(ScraperTestCase):
    def scene(self, *names):
        return {"id": "1", "files": [{"path": self.path(n)} for n in names]}

    def test_single_file_post(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - u_example_user.mp4"))
        self.assertEqual(self.output(proc), EXPECTED)

    def test_gallery_index_is_not_part_of_the_result(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - u_example_user - 2.mp4"))
        self.assertEqual(self.output(proc), EXPECTED)

    def test_title_containing_the_separator(self):
        proc = self.run_scraper("scene", self.scene("Part A - Part B - 2001-02-03 - u_example_user.mp4"))
        self.assertEqual(self.output(proc)["title"], "Part A - Part B")

    def test_performer_ending_in_digits_is_kept(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - u_example_user_1234.mp4"))
        self.assertEqual(
            self.output(proc)["performers"],
            [{"name": "u_example_user_1234", "urls": ["https://www.reddit.com/user/example_user_1234"]}],
        )

    def test_performer_without_the_u_prefix_gets_no_url(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - example_user.mp4"))
        self.assertEqual(self.output(proc)["performers"], [{"name": "example_user"}])

    def test_bare_u_prefix_gets_no_url(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - u_.mp4"))
        self.assertEqual(self.output(proc)["performers"], [{"name": "u_"}])

    def test_name_that_does_not_match_is_an_empty_update(self):
        proc = self.run_scraper("scene", self.scene("example clip.mp4"))
        self.assertEqual(self.output(proc), {})
        self.assertNotIn(ERROR, proc.stderr)

    def test_invalid_calendar_date_is_an_empty_update(self):
        proc = self.run_scraper("scene", self.scene("Example Post - 2001-02-30 - u_example_user.mp4"))
        self.assertEqual(self.output(proc), {})

    def test_later_file_is_used_when_the_first_does_not_match(self):
        proc = self.run_scraper(
            "scene",
            self.scene("example clip.mp4", "Example Post - 2001-02-03 - u_example_user.mp4"),
        )
        self.assertEqual(self.output(proc), EXPECTED)

    def test_first_matching_file_wins(self):
        proc = self.run_scraper(
            "scene",
            self.scene(
                "Example Post - 2001-02-03 - u_example_user.mp4",
                "Other Post - 2002-03-04 - u_other_user.mp4",
            ),
        )
        self.assertEqual(self.output(proc), EXPECTED)

    def test_file_outside_a_subreddit_folder_gets_no_studio(self):
        proc = self.run_scraper("scene", {"id": "1", "files": [{"path": self.path(FILE_NAME, "downloads")}]})
        self.assertEqual(self.output(proc), EXPECTED_NO_STUDIO)

    def test_scene_without_files_is_null_with_an_error(self):
        proc = self.run_scraper("scene", {"id": "1"})
        self.assertEqual(proc.stdout.strip(), "null")
        self.assertIn(ERROR, proc.stderr)

    def test_scene_never_calls_graphql(self):
        self.run_scraper("scene", self.scene("Example Post - 2001-02-03 - u_example_user.mp4"))
        self.assertEqual(self.graphql_calls(), [])

    def test_unknown_operation_fails(self):
        proc = self.run_scraper("gallery", {"id": "1"})
        self.assertNotEqual(proc.returncode, 0)


class ImageTests(ScraperTestCase):
    def lookup_result(self, *names):
        return {"findImage": {"visual_files": [{"path": self.path(n)} for n in names]}}

    def test_input_file_paths_are_used_without_a_lookup(self):
        fragment = {"id": "7", "files": [{"path": self.path("Example Post - 2001-02-03 - u_example_user - 1.jpg")}]}
        proc = self.run_scraper("image", fragment)
        self.assertEqual(self.output(proc), EXPECTED)
        self.assertEqual(self.graphql_calls(), [])

    def test_later_input_path_is_used_when_the_first_does_not_match(self):
        fragment = {
            "id": "7",
            "files": [
                {"path": self.path("example picture.jpg")},
                {"path": self.path("Example Post - 2001-02-03 - u_example_user.jpg")},
            ],
        }
        proc = self.run_scraper("image", fragment)
        self.assertEqual(self.output(proc), EXPECTED)
        self.assertEqual(self.graphql_calls(), [])

    def test_input_paths_that_do_not_match_are_an_empty_update_without_a_lookup(self):
        fragment = {"id": "7", "files": [{"path": self.path("example picture.jpg")}]}
        proc = self.run_scraper("image", fragment)
        self.assertEqual(self.output(proc), {})
        self.assertEqual(self.graphql_calls(), [])

    def test_input_without_file_paths_uses_the_lookup(self):
        result = self.lookup_result("Example Post - 2001-02-03 - u_example_user.jpg")
        proc = self.run_scraper("image", {"id": "7", "title": "example picture"}, graphql_result=result)
        self.assertEqual(self.output(proc), EXPECTED)
        self.assertEqual(self.graphql_calls(), [{"id": "7"}])

    def test_empty_input_file_list_uses_the_lookup(self):
        result = self.lookup_result("Example Post - 2001-02-03 - u_example_user.jpg")
        proc = self.run_scraper("image", {"id": "7", "files": []}, graphql_result=result)
        self.assertEqual(self.output(proc), EXPECTED)
        self.assertEqual(self.graphql_calls(), [{"id": "7"}])

    def test_every_looked_up_path_is_tried(self):
        result = self.lookup_result("example picture.jpg", "Example Post - 2001-02-03 - u_example_user.jpg")
        proc = self.run_scraper("image", {"id": "7"}, graphql_result=result)
        self.assertEqual(self.output(proc), EXPECTED)

    def test_failed_lookup_is_an_empty_update_with_an_error(self):
        proc = self.run_scraper("image", {"id": "7"}, graphql_result=None)
        self.assertEqual(self.output(proc), {})
        self.assertIn(ERROR, proc.stderr)
        self.assertIn("lookup failed", proc.stderr)
        self.assertNotIn("no files", proc.stderr)

    def test_lookup_that_raises_is_an_empty_update_with_an_error(self):
        proc = self.run_scraper("image", {"id": "7"}, graphql_raises=True)
        self.assertEqual(self.output(proc), {})
        self.assertIn(ERROR, proc.stderr)
        self.assertIn("lookup failed", proc.stderr)
        self.assertIn("connection refused", proc.stderr)

    def test_image_with_no_files_is_an_empty_update_with_a_warning(self):
        proc = self.run_scraper("image", {"id": "7"}, graphql_result={"findImage": {"visual_files": []}})
        self.assertEqual(self.output(proc), {})
        self.assertIn(WARNING, proc.stderr)
        self.assertIn("no files", proc.stderr)
        self.assertNotIn("lookup failed", proc.stderr)
        self.assertNotIn(ERROR, proc.stderr)

    def test_unknown_image_is_treated_as_having_no_files(self):
        proc = self.run_scraper("image", {"id": "7"}, graphql_result={"findImage": None})
        self.assertEqual(self.output(proc), {})
        self.assertIn("no files", proc.stderr)

    def test_missing_id_is_null(self):
        proc = self.run_scraper("image", {})
        self.assertEqual(proc.stdout.strip(), "null")
        self.assertIn(ERROR, proc.stderr)
        self.assertEqual(self.graphql_calls(), [])


class MetadataTests(ScraperTestCase):
    def scrape(self, operation, paths):
        fragment = {"id": "1", "files": [{"path": p} for p in paths]}
        return self.output(self.run_scraper(operation, fragment))

    def test_scene_reads_the_metadata_file(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata())
        self.assertEqual(self.scrape("scene", [media]), EXPECTED_FROM_METADATA)

    def test_image_with_input_paths_reads_the_metadata_file(self):
        media = self.write_metadata(self.path("Example Post - 2001-02-03 - u_example_user.jpg"), reddit_metadata())
        self.assertEqual(self.scrape("image", [media]), EXPECTED_FROM_METADATA)
        self.assertEqual(self.graphql_calls(), [])

    def test_image_via_lookup_reads_the_metadata_file(self):
        media = self.write_metadata(self.path("Example Post - 2001-02-03 - u_example_user.jpg"), reddit_metadata())
        result = {"findImage": {"visual_files": [{"path": media}]}}
        proc = self.run_scraper("image", {"id": "7"}, graphql_result=result)
        self.assertEqual(self.output(proc), EXPECTED_FROM_METADATA)

    def test_metadata_wins_over_the_file_name(self):
        # The file name differs from the post: sanitized title, other folder
        media = self.write_metadata(
            self.path("Example Post_ the full title_ - 2001-02-03 - u_example_user.mp4", "downloads"),
            reddit_metadata(),
        )
        self.assertEqual(self.scrape("scene", [media]), EXPECTED_FROM_METADATA)

    def test_metadata_works_for_any_file_name(self):
        media = self.write_metadata(self.path("abc123 example.mp4", "downloads"), reddit_metadata())
        self.assertEqual(self.scrape("scene", [media]), EXPECTED_FROM_METADATA)

    def test_unicode_is_kept(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(title="Caf\u00e9 \U0001f525"))
        self.assertEqual(self.scrape("scene", [media])["title"], "Caf\u00e9 \U0001f525")

    def test_empty_post_text_is_left_out(self):
        for text in ("", "   \n "):
            media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(selftext=text))
            self.assertNotIn("details", self.scrape("scene", [media]))

    def test_missing_post_text_is_left_out(self):
        meta = reddit_metadata()
        del meta["selftext"]
        media = self.write_metadata(self.path(FILE_NAME), meta)
        self.assertNotIn("details", self.scrape("scene", [media]))

    def test_missing_flair_is_left_out(self):
        for flair in (None, "", "  "):
            media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(link_flair_text=flair))
            self.assertNotIn("tags", self.scrape("scene", [media]))

    def test_flair_is_kept_as_written(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(link_flair_text=" Example Flair 10 "))
        self.assertEqual(self.scrape("scene", [media])["tags"], [{"name": "Example Flair 10"}])

    def test_performer_name_keeps_the_u_prefix(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(author="other_user"))
        self.assertEqual(
            self.scrape("scene", [media])["performers"],
            [{"name": "u_other_user", "urls": ["https://www.reddit.com/user/other_user"]}],
        )

    def test_deleted_author_gives_no_performer(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(author="[deleted]"))
        self.assertNotIn("performers", self.scrape("scene", [media]))

    def test_date_is_the_utc_post_date(self):
        # 23:30 UTC stays on the 3rd, matching the date gallery-dl writes in file names
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata(date="2001-02-03 23:30:00"))
        self.assertEqual(self.scrape("scene", [media])["date"], "2001-02-03")

    def test_date_falls_back_to_created_utc(self):
        meta = reddit_metadata(created_utc=981244800.0)  # 2001-02-04 00:00:00 UTC
        del meta["date"]
        media = self.write_metadata(self.path(FILE_NAME), meta)
        self.assertEqual(self.scrape("scene", [media])["date"], "2001-02-04")

    def test_unusable_date_is_left_out(self):
        meta = reddit_metadata(date="not a date")
        del meta["created_utc"]
        media = self.write_metadata(self.path(FILE_NAME), meta)
        self.assertNotIn("date", self.scrape("scene", [media]))

    def test_missing_fields_are_left_out(self):
        media = self.write_metadata(self.path(FILE_NAME), {"category": "reddit", "title": "Example Post"})
        self.assertEqual(self.scrape("scene", [media]), {"title": "Example Post"})

    def test_metadata_with_no_usable_fields_falls_back_to_the_file_name(self):
        media = self.write_metadata(self.path(FILE_NAME), {"category": "reddit", "title": " "})
        self.assertEqual(self.scrape("scene", [media]), EXPECTED)

    def test_unmapped_fields_stay_unmapped(self):
        media = self.write_metadata(self.path(FILE_NAME), reddit_metadata())
        scraped = self.scrape("scene", [media])
        self.assertNotIn("photographer", scraped)
        self.assertNotIn("i.example.com", json.dumps(scraped))
        self.assertNotIn("over_18", json.dumps(scraped))

    def test_missing_metadata_file_falls_back_to_the_file_name(self):
        self.assertEqual(self.scrape("scene", [self.path(FILE_NAME)]), EXPECTED)

    def test_redgifs_metadata_falls_back_to_the_file_name(self):
        meta = {"category": "redgifs", "subcategory": "image", "id": "examplegif", "userName": "example_gif_user",
                "tags": ["Example Tag"], "date": "2005-06-07 08:09:10"}
        media = self.write_metadata(self.path(FILE_NAME), meta)
        self.assertEqual(self.scrape("scene", [media]), EXPECTED)

    def test_info_json_files_are_not_read(self):
        media = self.path(FILE_NAME)
        os.makedirs(os.path.dirname(media), exist_ok=True)
        for name in ("info.json", "examplegif.info.json", "Example Post - 2001-02-03 - u_example_user.info.json"):
            with open(os.path.join(os.path.dirname(media), name), "w", encoding="utf-8") as f:
                json.dump(reddit_metadata(title="Wrong Post"), f)
        self.assertEqual(self.scrape("scene", [media]), EXPECTED)

    def test_malformed_metadata_file_falls_back_with_a_warning(self):
        media = self.write_metadata(self.path(FILE_NAME), None, raw="{not json")
        proc = self.run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(self.output(proc), EXPECTED)
        self.assertIn(WARNING, proc.stderr)

    def test_metadata_that_is_not_an_object_falls_back(self):
        media = self.write_metadata(self.path(FILE_NAME), ["reddit"])
        self.assertEqual(self.scrape("scene", [media]), EXPECTED)

    def test_later_file_with_metadata_is_used(self):
        first = self.path("example clip.mp4")
        second = self.write_metadata(self.path("abc123 example.mp4"), reddit_metadata())
        self.assertEqual(self.scrape("scene", [first, second]), EXPECTED_FROM_METADATA)

    def test_nothing_usable_is_an_empty_update(self):
        self.assertEqual(self.scrape("scene", [self.path("example clip.mp4")]), {})


if __name__ == "__main__":
    unittest.main()
