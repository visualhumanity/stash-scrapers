import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock
from zoneinfo import ZoneInfo

import GalleryDlTwitter
from GalleryDlTwitter import (
    local_zone,
    make_tags,
    make_title,
    media_suffix,
    parse_date,
    poster_handle,
    run_image,
    scrape_metadata,
)

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "GalleryDlTwitter.py")

# 2^53 + 1: a float round-trip would turn this into 9007199254740992
TWEET_ID = 9007199254740993
TWEET_ID_TEXT = "9007199254740993"

# All sample data in this file is made up
SAMPLE_DATE = "2001-02-03 12:00:00"
SAMPLE_DAY = "2001-02-03"
# 02:30 UTC on the 4th is 21:30 on the 3rd in Toronto (EST, UTC-5)
LATE_UTC_DATE = "2001-02-04 02:30:00"

UTC = ZoneInfo("UTC")
TORONTO = ZoneInfo("America/Toronto")


def sidecar(**overrides):
    meta = {
        "bitrate": 1000,
        "duration": 1.5,
        "type": "video",
        "width": 640,
        "height": 480,
        "description": None,
        "sensitive_flags": [],
        "source_id": 1,
        "tweet_id": TWEET_ID,
        "retweet_id": 0,
        "quote_id": 0,
        "reply_id": 0,
        "conversation_id": TWEET_ID,
        "date": SAMPLE_DATE,
        "author": {"id": 1, "name": "example_user", "nick": "Example"},
        "user": {"id": 1, "name": "example_user", "nick": "Example"},
        "lang": "en",
        "sensitive": False,
        "content": "a caption",
        "count": 1,
        "category": "twitter",
        "subcategory": "timeline",
        "num": 1,
        "filename": "AbCdEfGh",
        "extension": "mp4",
    }
    meta.update(overrides)
    return meta


def run_scraper(operation, fragment, tz="America/Toronto"):
    """Run the scraper as Stash would: JSON on stdin, JSON on stdout."""
    env = {k: v for k, v in os.environ.items() if k != "TZ"}
    if tz is not None:
        env["TZ"] = tz
    return subprocess.run(
        [sys.executable, "-B", SCRIPT, operation],
        input=json.dumps(fragment),
        capture_output=True,
        text=True,
        env=env,
    )


class LocalZoneTests(unittest.TestCase):
    def zone_with_tz(self, tz):
        env = {k: v for k, v in os.environ.items() if k != "TZ"}
        if tz is not None:
            env["TZ"] = tz
        with mock.patch.dict(os.environ, env, clear=True):
            return local_zone()

    def test_uses_container_tz(self):
        self.assertEqual(self.zone_with_tz("Pacific/Auckland").key, "Pacific/Auckland")

    def test_unset_falls_back_to_toronto(self):
        self.assertEqual(self.zone_with_tz(None).key, "America/Toronto")

    def test_empty_falls_back_to_toronto(self):
        self.assertEqual(self.zone_with_tz("").key, "America/Toronto")

    def test_unknown_zone_falls_back_to_toronto(self):
        self.assertEqual(self.zone_with_tz("Not/AZone").key, "America/Toronto")


class ParseDateTests(unittest.TestCase):
    def test_strips_time(self):
        self.assertEqual(parse_date(SAMPLE_DATE, UTC), SAMPLE_DAY)

    def test_converts_from_utc_to_the_zone(self):
        self.assertEqual(parse_date(LATE_UTC_DATE, TORONTO), "2001-02-03")
        self.assertEqual(parse_date(LATE_UTC_DATE, UTC), "2001-02-04")

    def test_conversion_can_move_the_date_forward(self):
        self.assertEqual(parse_date("2001-02-03 20:00:00", ZoneInfo("Asia/Tokyo")), "2001-02-04")

    def test_invalid_date(self):
        self.assertIsNone(parse_date("2001-13-45 00:00:00", UTC))

    def test_date_without_time_is_rejected(self):
        self.assertIsNone(parse_date(SAMPLE_DAY, UTC))

    def test_non_string(self):
        self.assertIsNone(parse_date(None, UTC))

    def test_no_zone_leaves_date_out(self):
        self.assertIsNone(parse_date(SAMPLE_DATE, None))


class MediaSuffixTests(unittest.TestCase):
    def test_multi_media_tweet(self):
        self.assertEqual(media_suffix({"num": 2, "count": 4}), " [2]")

    def test_single_media_tweet(self):
        self.assertEqual(media_suffix({"num": 1, "count": 1}), "")

    def test_missing_or_invalid_values(self):
        self.assertEqual(media_suffix({}), "")
        self.assertEqual(media_suffix({"count": 3}), "")
        self.assertEqual(media_suffix({"num": 2}), "")
        self.assertEqual(media_suffix({"num": 0, "count": 3}), "")
        self.assertEqual(media_suffix({"num": True, "count": 3}), "")
        self.assertEqual(media_suffix({"num": "2", "count": "3"}), "")


class MakeTitleTests(unittest.TestCase):
    def test_plain_caption(self):
        self.assertEqual(make_title("a caption"), "a caption")

    def test_only_the_first_line_is_used(self):
        self.assertEqual(make_title("line one\nline two\n\nline three"), "line one")

    def test_leading_blank_lines_are_skipped(self):
        self.assertEqual(make_title("\n  \n  first real line \nsecond"), "first real line")

    def test_empty_caption_gives_no_title(self):
        self.assertIsNone(make_title(""))
        self.assertIsNone(make_title("  \n "))
        self.assertIsNone(make_title(None))

    def test_empty_caption_gets_no_bare_suffix(self):
        self.assertIsNone(make_title("", " [2]"))

    def test_emoji_are_kept(self):
        self.assertEqual(make_title("café \U0001f525\U0001f525"), "café \U0001f525\U0001f525")

    def test_exactly_at_the_limit_is_untouched(self):
        line = "x" * 120
        self.assertEqual(make_title(line), line)

    def test_long_caption_is_cut_at_a_word_boundary(self):
        title = make_title("word " * 100)
        self.assertLessEqual(len(title), 120)
        self.assertTrue(title.endswith("word…"))

    def test_half_cut_word_is_dropped(self):
        line = ("a" * 10 + " ") * 11 + "bbbbbbbbbbbbbbbbbbbbbb"
        title = make_title(line)
        self.assertEqual(title, ("a" * 10 + " ") * 9 + "a" * 10 + "…")
        self.assertLessEqual(len(title), 120)

    def test_cut_falling_on_a_space_keeps_the_whole_word(self):
        title = make_title("a" * 119 + " bbb")
        self.assertEqual(title, "a" * 119 + "…")
        self.assertEqual(len(title), 120)

    def test_single_long_word_is_cut_hard(self):
        title = make_title("x" * 300)
        self.assertEqual(title, "x" * 119 + "…")

    def test_suffix_counts_towards_the_limit(self):
        title = make_title("word " * 100, " [12]")
        self.assertLessEqual(len(title), 120)
        self.assertTrue(title.endswith("word… [12]"))

    def test_short_caption_gets_the_suffix(self):
        self.assertEqual(make_title("hello", " [3]"), "hello [3]")


class PosterHandleTests(unittest.TestCase):
    def test_prefers_author(self):
        meta = {"author": {"name": "poster"}, "user": {"name": "folder"}}
        self.assertEqual(poster_handle(meta), "poster")

    def test_falls_back_to_user_when_author_is_empty(self):
        meta = {"author": {}, "user": {"name": "folder"}}
        self.assertEqual(poster_handle(meta), "folder")

    def test_none_when_absent(self):
        self.assertIsNone(poster_handle({}))


class MakeTagsTests(unittest.TestCase):
    def test_dedupes_case_insensitively_and_keeps_order(self):
        self.assertEqual(
            make_tags(["Alpha", "beta", "alpha", " "]),
            [{"name": "Alpha"}, {"name": "beta"}],
        )

    def test_missing_hashtags(self):
        self.assertEqual(make_tags(None), [])


class ScrapeMetadataTests(unittest.TestCase):
    def test_full_post(self):
        meta = sidecar(content="hello\nworld", hashtags=["one", "two"])
        profile = "https://twitter.com/example_user"
        self.assertEqual(
            scrape_metadata(meta, UTC),
            {
                "title": "hello",
                "details": "hello\nworld",
                "date": SAMPLE_DAY,
                "code": TWEET_ID_TEXT,
                "urls": [f"https://twitter.com/example_user/status/{TWEET_ID_TEXT}"],
                "performers": [{"name": "example_user", "urls": [profile]}],
                "studio": {"name": "example_user", "urls": [profile]},
                "tags": [{"name": "one"}, {"name": "two"}],
            },
        )

    def test_tweet_id_is_not_rounded(self):
        self.assertEqual(scrape_metadata(sidecar(), UTC)["code"], "9007199254740993")

    def test_date_uses_the_given_zone(self):
        meta = sidecar(date=LATE_UTC_DATE)
        self.assertEqual(scrape_metadata(meta, TORONTO)["date"], "2001-02-03")

    def test_multi_media_tweet_title_gets_an_index(self):
        scraped = scrape_metadata(sidecar(content="caption\nmore", num=3, count=4), UTC)
        self.assertEqual(scraped["title"], "caption [3]")
        self.assertEqual(scraped["details"], "caption\nmore")

    def test_empty_caption_leaves_title_and_details_out(self):
        scraped = scrape_metadata(sidecar(content="", num=2, count=3), UTC)
        self.assertNotIn("title", scraped)
        self.assertNotIn("details", scraped)
        self.assertEqual(scraped["date"], SAMPLE_DAY)

    def test_empty_author_uses_user(self):
        scraped = scrape_metadata(sidecar(author={}), UTC)
        self.assertEqual(scraped["performers"][0]["name"], "example_user")
        self.assertEqual(scraped["studio"]["name"], "example_user")

    def test_no_handle_still_builds_a_status_url(self):
        scraped = scrape_metadata(sidecar(author={}, user={}), UTC)
        self.assertEqual(scraped["urls"], [f"https://twitter.com/i/status/{TWEET_ID_TEXT}"])
        self.assertNotIn("performers", scraped)
        self.assertNotIn("studio", scraped)

    def test_missing_fields_are_left_out_not_emptied(self):
        scraped = scrape_metadata({"content": "x"}, UTC)
        self.assertEqual(scraped, {"title": "x", "details": "x"})

    def test_no_time_zone_data_leaves_date_out(self):
        self.assertNotIn("date", scrape_metadata(sidecar(), None))

    def test_unmapped_fields_stay_unmapped(self):
        scraped = scrape_metadata(sidecar(description="alt text", lang="en", sensitive=True), UTC)
        for key in ("director", "photographer", "image", "groups", "rating"):
            self.assertNotIn(key, scraped)
        self.assertNotIn("alt text", json.dumps(scraped))


class HarnessTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, meta):
        path = os.path.join(self.dir.name, name)
        # Matches gallery-dl's own formatting, which keeps non-ASCII characters raw
        with open(path + ".json", "w", encoding="utf-8") as f:
            json.dump(meta, f, indent=4, ensure_ascii=False)
        return path

    def test_scene_reads_sidecar(self):
        media = self.write("clip.mp4", sidecar(content="café \U0001f525"))
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        out = json.loads(proc.stdout)
        self.assertEqual(out["title"], "café \U0001f525")
        self.assertEqual(out["details"], "café \U0001f525")
        self.assertEqual(out["code"], TWEET_ID_TEXT)

    def test_scene_date_follows_container_tz(self):
        media = self.write("clip.mp4", sidecar(date=LATE_UTC_DATE))
        fragment = {"id": "1", "files": [{"path": media}]}
        self.assertEqual(json.loads(run_scraper("scene", fragment, tz="America/Toronto").stdout)["date"], "2001-02-03")
        self.assertEqual(json.loads(run_scraper("scene", fragment, tz="UTC").stdout)["date"], "2001-02-04")

    def test_unset_tz_falls_back_without_an_error_log(self):
        media = self.write("clip.mp4", sidecar(date=LATE_UTC_DATE))
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]}, tz=None)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["date"], "2001-02-03")
        self.assertNotIn("\x01e\x02", proc.stderr)
        self.assertNotIn("\x01w\x02", proc.stderr)

    def test_uses_first_file_that_has_a_sidecar(self):
        missing = os.path.join(self.dir.name, "no-sidecar.mp4")
        media = self.write("has-sidecar.mp4", sidecar())
        proc = run_scraper("scene", {"id": "1", "files": [{"path": missing}, {"path": media}]})
        self.assertEqual(json.loads(proc.stdout)["code"], TWEET_ID_TEXT)

    def test_missing_sidecar_is_empty_update_and_quiet(self):
        media = os.path.join(self.dir.name, "no-sidecar.mp4")
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})
        self.assertNotIn("\x01e\x02", proc.stderr)
        self.assertNotIn("\x01w\x02", proc.stderr)

    def test_avatar_sidecar_is_skipped(self):
        media = self.write("avatar.jpg", sidecar(subcategory="avatar", content="x"))
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(json.loads(proc.stdout), {})

    def test_background_sidecar_is_skipped(self):
        media = self.write("background.jpg", sidecar(subcategory="background", content="x"))
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(json.loads(proc.stdout), {})

    def test_malformed_sidecar_is_empty_update_with_a_warning(self):
        media = os.path.join(self.dir.name, "bad.mp4")
        with open(media + ".json", "w", encoding="utf-8") as f:
            f.write("{not json")
        proc = run_scraper("scene", {"id": "1", "files": [{"path": media}]})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout), {})
        self.assertIn("\x01w\x02", proc.stderr)
        self.assertNotIn("\x01e\x02", proc.stderr)

    def test_scene_without_files_is_null_with_an_error(self):
        proc = run_scraper("scene", {"id": "1"})
        self.assertEqual(proc.stdout.strip(), "null")
        self.assertIn("\x01e\x02", proc.stderr)

    def test_unknown_operation_fails(self):
        proc = run_scraper("gallery", {"id": "1"})
        self.assertNotEqual(proc.returncode, 0)


class ImageTests(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.dir.cleanup)

    def write(self, name, meta):
        path = os.path.join(self.dir.name, name)
        with open(path + ".json", "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False)
        return path

    def scrape(self, fragment, paths):
        out = io.StringIO()
        with mock.patch.object(GalleryDlTwitter, "get_image_paths", return_value=paths) as lookup:
            with contextlib.redirect_stdout(out):
                run_image(fragment)
        return out.getvalue(), lookup

    def test_image_is_read_through_the_graphql_lookup(self):
        media = self.write("pic.jpg", sidecar(type="photo", extension="jpg", content="pic", num=2, count=4))
        out, lookup = self.scrape({"id": "7", "files": [{"path": "dummy/ignored.jpg"}]}, [media])
        lookup.assert_called_once_with("7")
        scraped = json.loads(out)
        self.assertEqual(scraped["title"], "pic [2]")
        self.assertEqual(scraped["code"], TWEET_ID_TEXT)
        self.assertNotIn("photographer", scraped)

    def test_failed_lookup_is_an_empty_update(self):
        out, _ = self.scrape({"id": "7"}, None)
        self.assertEqual(json.loads(out), {})

    def test_image_with_no_files_is_an_empty_update(self):
        out, _ = self.scrape({"id": "7"}, [])
        self.assertEqual(json.loads(out), {})

    def test_avatar_image_is_skipped(self):
        media = self.write("avatar.jpg", sidecar(subcategory="avatar"))
        out, _ = self.scrape({"id": "7"}, [media])
        self.assertEqual(json.loads(out), {})

    def test_missing_id_is_null(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out), self.assertRaises(SystemExit) as raised:
            run_image({})
        self.assertEqual(raised.exception.code, 0)
        self.assertEqual(out.getvalue().strip(), "null")


class GetImagePathsTests(unittest.TestCase):
    def lookup(self, result):
        fake = types.ModuleType("py_common.graphql")
        fake.callGraphQL = mock.Mock(return_value=result)
        with mock.patch.dict(sys.modules, {"py_common.graphql": fake}):
            return GalleryDlTwitter.get_image_paths("7"), fake.callGraphQL

    def test_returns_visual_file_paths(self):
        result = {"findImage": {"visual_files": [{"path": "dummy/one.jpg"}, {"path": "dummy/two.jpg"}]}}
        paths, call = self.lookup(result)
        self.assertEqual(paths, ["dummy/one.jpg", "dummy/two.jpg"])
        self.assertEqual(call.call_args.args[1], {"id": "7"})

    def test_failed_lookup_is_none(self):
        self.assertIsNone(self.lookup(None)[0])

    def test_unknown_image_has_no_paths(self):
        self.assertEqual(self.lookup({"findImage": None})[0], [])


if __name__ == "__main__":
    unittest.main()
