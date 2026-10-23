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

    def path(self, name):
        return os.path.join(self.dir, "r_ExampleSub", name)

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


EXPECTED = {
    "title": "Example Post",
    "date": "2001-02-03",
    "performers": [{"name": "u_example_user"}],
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
        self.assertEqual(self.output(proc)["performers"], [{"name": "u_example_user_1234"}])

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


if __name__ == "__main__":
    unittest.main()
