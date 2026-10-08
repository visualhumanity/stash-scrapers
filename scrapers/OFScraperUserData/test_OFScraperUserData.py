import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.realpath(__file__))
SCRIPT_NAME = "OFScraperUserData.py"
COMMUNITY = os.path.join(os.path.dirname(HERE), "community")
CONVERTER = os.path.join(os.path.dirname(HERE), "ConvertHtmlToMarkdown")

# All data in this file is made up.
SCHEMA = """
CREATE TABLE medias (id INTEGER PRIMARY KEY, media_id INTEGER, post_id INTEGER, link VARCHAR,
  directory VARCHAR, filename VARCHAR, size INTEGER, api_type VARCHAR, media_type VARCHAR,
  preview INTEGER, linked BOOL, downloaded BOOL, created_at TIMESTAMP, posted_at TIMESTAMP,
  duration VARCHAR, unlocked BOOL, hash VARCHAR, model_id INTEGER);
CREATE TABLE posts (id INTEGER PRIMARY KEY, post_id INTEGER, text VARCHAR, price INTEGER, paid INTEGER,
  archived BOOLEAN, pinned BOOLEAN, stream BOOLEAN, opened BOOLEAN, created_at TIMESTAMP,
  model_id INTEGER, is_deleted BOOLEAN);
CREATE TABLE messages (id INTEGER PRIMARY KEY, post_id INTEGER, text VARCHAR, price INTEGER,
  paid BOOLEAN, archived BOOLEAN, created_at TIMESTAMP, user_id INTEGER, model_id INTEGER,
  is_deleted BOOLEAN);
CREATE TABLE stories (id INTEGER PRIMARY KEY, post_id INTEGER, text VARCHAR, price INTEGER,
  paid INTEGER, archived BOOLEAN, created_at TIMESTAMP, model_id INTEGER);
"""

TABLE_FOR = {
    "Timeline": "posts", "Archived": "posts", "Pinned": "posts", "Paid": "posts",
    "Message": "messages", "Messages": "messages",
    "Highlights": "stories", "Stories": "stories",
}
RESPONSE_DIR = {
    "Timeline": "Posts", "Pinned": "Posts", "Paid": "Posts", "Archived": "Archived",
    "Message": "Messages", "Messages": "Messages", "Highlights": "Stories", "Stories": "Stories",
}


class Sandbox:
    """A fake download root plus a private copy of the scraper, so the cache file stays in the sandbox."""

    def __init__(self, with_converter=True):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "download")
        os.makedirs(os.path.join(self.root, ".data"))
        scrapers = os.path.join(self.tmp, "scrapers")
        self.scraper_dir = os.path.join(scrapers, "OFScraperUserData")
        os.makedirs(self.scraper_dir)
        shutil.copy(os.path.join(HERE, SCRIPT_NAME), self.scraper_dir)
        os.symlink(COMMUNITY, os.path.join(scrapers, "community"))
        if with_converter:
            os.symlink(CONVERTER, os.path.join(scrapers, "ConvertHtmlToMarkdown"))
        self.script = os.path.join(self.scraper_dir, SCRIPT_NAME)
        self.cache_path = os.path.join(self.scraper_dir, "cache_db_location.json")

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def db(self, username, account_id=1):
        folder = os.path.join(self.root, ".data", f"{username}_{account_id}")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, "user_data.db")
        if not os.path.exists(path):
            con = sqlite3.connect(path)
            con.executescript(SCHEMA)
            con.close()
        return path

    def add_media(self, db_path, media_id, post_id, api_type, text, created_at,
                  filename=None, media_type="Videos"):
        """Insert a media row and its source row; returns the filename."""
        filename = filename or f"2001-02-03 - caption [orig_{media_id}].mp4"
        table = TABLE_FOR[api_type]
        con = sqlite3.connect(db_path)
        con.execute(
            "INSERT INTO medias (media_id, post_id, filename, api_type, media_type, downloaded) "
            "VALUES (?, ?, ?, ?, ?, 1)",
            (media_id, post_id, filename, api_type, media_type),
        )
        if table is not None and created_at is not None:
            con.execute(f"INSERT INTO {table} (post_id, text, created_at) VALUES (?, ?, ?)",
                        (post_id, text, created_at))
        con.commit()
        con.close()
        return filename

    def video_path(self, model_folder, api_type, filename):
        folder = os.path.join(self.root, model_folder, RESPONSE_DIR[api_type], "Videos")
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, filename)
        open(path, "w").close()
        return path

    def run(self, path, tz="UTC", fragment=None):
        env = {k: v for k, v in os.environ.items() if k != "TZ"}
        if tz is not None:
            env["TZ"] = tz
        fragment = fragment if fragment is not None else {"id": "1", "files": [{"path": path}]}
        proc = subprocess.run(
            [sys.executable, "-B", self.script],
            input=json.dumps(fragment), capture_output=True, text=True, env=env,
        )
        out = proc.stdout.strip()
        return json.loads(out) if out else None, proc

    def scrape(self, model_folder, db_username, media_id, post_id, api_type, text, created_at,
               filename=None, tz="UTC"):
        """Create the media + post + file, then scrape it."""
        db_path = self.db(db_username)
        filename = self.add_media(db_path, media_id, post_id, api_type, text, created_at, filename)
        path = self.video_path(model_folder, api_type, filename)
        return self.run(path, tz=tz)[0]


class Base(unittest.TestCase):
    def setUp(self):
        self.box = Sandbox()
        self.addCleanup(self.box.cleanup)


class TimelinePostTests(Base):
    def test_timeline_post_fills_date_studio_performer_url_and_details(self):
        result = self.box.scrape(
            "Example Name (examplestudio)", "examplestudio", media_id=555, post_id=9001,
            api_type="Timeline", text="<p>Hello there</p>", created_at="2001-02-03T12:00:00+00:00",
        )
        self.assertEqual(result, {
            "date": "2001-02-03",
            "studio": {"name": "examplestudio"},
            "performers": [{"name": "Example Name"}],
            "urls": ["https://onlyfans.com/9001/examplestudio"],
            "title": "Hello there",
            "details": "Hello there",
        })


class SourceTableTests(Base):
    def test_message_and_story_have_no_url(self):
        for api_type, post_id in (("Messages", 7001), ("Stories", 7002)):
            with self.subTest(api_type=api_type):
                result = self.box.scrape(
                    "Example Name (examplestudio)", "examplestudio", media_id=post_id + 1,
                    post_id=post_id, api_type=api_type, text="hi",
                    created_at="2001-02-03T12:00:00+00:00",
                )
                self.assertNotIn("urls", result)
                self.assertEqual(result["details"], "hi")
                self.assertEqual(result["date"], "2001-02-03")

    def test_same_post_id_in_two_tables_uses_api_type(self):
        db = self.box.db("examplestudio")
        con = sqlite3.connect(db)
        con.execute("INSERT INTO messages (post_id, text, created_at) VALUES (5, 'message text', '2001-01-01T00:00:00+00:00')")
        con.commit()
        con.close()
        result = self.box.scrape(
            "Example Name (examplestudio)", "examplestudio", media_id=50, post_id=5,
            api_type="Timeline", text="post text", created_at="2002-02-02T00:00:00+00:00",
        )
        self.assertEqual(result["details"], "post text")
        self.assertEqual(result["date"], "2002-02-02")


class DateTests(Base):
    def test_date_converted_to_container_timezone(self):
        args = dict(media_id=60, post_id=60, api_type="Timeline", text="x",
                    created_at="2001-02-03T02:30:00+00:00")
        result = self.box.scrape("Example Name (examplestudio)", "examplestudio",
                                 tz="America/Toronto", **args)
        self.assertEqual(result["date"], "2001-02-02")


class NoMatchTests(Base):
    def test_unknown_media_gives_empty_object(self):
        self.box.db("examplestudio")
        path = self.box.video_path("Example Name (examplestudio)", "Timeline",
                                   "2001-02-03 - x [orig_999].mp4")
        self.assertEqual(self.box.run(path)[0], {})

    def test_path_outside_model_folder_gives_empty_object(self):
        self.assertEqual(self.box.run("/data/example/video.mp4")[0], {})

    def test_empty_text_omits_details(self):
        result = self.box.scrape("Example Name (examplestudio)", "examplestudio", media_id=70,
                                 post_id=70, api_type="Timeline", text="",
                                 created_at="2001-02-03T12:00:00+00:00")
        self.assertNotIn("details", result)


class DescriptionTests(Base):
    def details(self, text, box=None):
        box = box or self.box
        return box.scrape("Example Name (examplestudio)", "examplestudio", media_id=85,
                          post_id=85, api_type="Timeline", text=text,
                          created_at="2001-02-03T12:00:00+00:00")["details"]

    def test_html_description_becomes_markdown_with_absolute_links(self):
        text = '<p>Hi <b>all</b><br>see <a href="/linkeduser">@linkeduser</a> or <a href="https://example.com/x">site</a></p>'
        self.assertEqual(
            self.details(text),
            "Hi **all**\nsee [@linkeduser](https://onlyfans.com/linkeduser) or [site](https://example.com/x)",
        )

    def test_plain_text_description_is_unchanged(self):
        self.assertEqual(self.details("5 < 10 and plain"), "5 < 10 and plain")

    def test_missing_converter_keeps_html(self):
        box = Sandbox(with_converter=False)
        self.addCleanup(box.cleanup)
        self.assertEqual(self.details("<p>Hi</p>", box), "<p>Hi</p>")


class TitleTests(Base):
    next_id = 1000

    def result(self, text, api_type="Timeline"):
        TitleTests.next_id += 1
        return self.box.scrape("Example Name (examplestudio)", "examplestudio",
                               media_id=TitleTests.next_id, post_id=TitleTests.next_id,
                               api_type=api_type, text=text,
                               created_at="2001-02-03T12:00:00+00:00")

    def title(self, text, api_type="Timeline"):
        return self.result(text, api_type).get("title")

    def check(self, cases):
        for text, expected in cases:
            with self.subTest(text=text):
                self.assertEqual(self.title(text), expected)

    def test_short_line_is_the_whole_title_and_emoji_stay(self):
        self.check([("Pool day 🌊", "Pool day 🌊")])

    def test_first_html_paragraph_or_line_is_the_candidate(self):
        self.check([
            ("<p>Morning stretch 🧘</p><p>Second paragraph here</p>", "Morning stretch 🧘"),
            ("First line<br />Second line", "First line"),
            ("First line<br>Second line", "First line"),
            ("<p>Fish &amp; chips</p>", "Fish & chips"),
        ])

    def test_no_usable_text_gives_no_title(self):
        for text in (None, "", "   ", "🌊💦", "<p></p>"):
            with self.subTest(text=text):
                self.assertNotIn("title", self.result(text))

    def test_title_ends_at_the_first_segment_of_30_characters(self):
        self.check([
            ("Pool boy shows his best splash and dives in 🏊💦 do you like when I swim? Tell me 😘",
             "Pool boy shows his best splash and dives in 🏊💦"),
            ("Trying my robe 💕 it’s so soft, but then it got too warm and I had to take it off 🤭 enjoy babes 😘",
             "Trying my robe 💕 it’s so soft, but then it got too warm and I had to take it off 🤭"),
            ("Lazy Sunday in bed. Come cuddle with me. Missing you all",
             "Lazy Sunday in bed. Come cuddle with me"),
            ("Wait for it... then he cums all over 💦 so good",
             "Wait for it... then he cums all over 💦"),
            ("Big news! Videos every week, so subscribe", "Big news! Videos every week, so subscribe"),
        ])

    def test_abbreviations_numbers_and_handles_do_not_end_a_segment(self):
        self.check([
            ("Morning workout with the crew, min. 20 of cardio. Then more",
             "Morning workout with the crew, min. 20 of cardio"),
            ("Rated 4.5 stars by everybody who watched it! Thanks",
             "Rated 4.5 stars by everybody who watched it!"),
        ])

    def test_emoji_sequences_are_never_split(self):
        text = "Long walk through the park today 👩🏽‍❤️‍👨🏽 and then we went home"
        self.assertEqual(self.title(text), "Long walk through the park today 👩🏽‍❤️‍👨🏽")

    def test_cjk_punctuation_ends_a_segment_without_spaces(self):
        sentence = "楽しい一日でした" * 4
        self.check([(sentence + "。明日もよろしくお願いします", sentence)])

    def test_filler_is_removed_before_the_title_is_chosen(self):
        self.check([
            ("Shower solo 🚿 tip $5 for more", "Shower solo 🚿"),
            ("Hey! New scene is up, link below", "Hey! New scene is up"),
            ("Thanks for subscribing! Morning stretch with the whole crew", "Morning stretch with the whole crew"),
            ("FREE: 12 MIN - Morning stretch", "Morning stretch"),
            ("Surprise 🎁", "Surprise 🎁"),
        ])
        for text in ("Thanks for subscribing!", "Link in bio", "Stream started at 5pm"):
            with self.subTest(text=text):
                self.assertNotIn("title", self.result(text))

    def test_filler_only_first_line_moves_to_the_next_line(self):
        self.assertEqual(self.title("<p>Link in bio</p><p>Morning stretch</p>"), "Morning stretch")

    def test_cleanup(self):
        self.check([
            ("**Morning stretch**", "Morning stretch"),
            ("Morning   stretch.", "Morning stretch"),
            ("Morning stretch!", "Morning stretch!"),
            ("Wait for it...", "Wait for it..."),
            ("New scene with @example_user,", "New scene with @example_user"),
            ("Watch here https://example.com/x", "Watch here"),
        ])

    def test_all_caps_becomes_title_case_but_mixed_case_is_kept(self):
        self.check([
            ("MORNING STRETCH PT. 2 - SOLO", "Morning Stretch PT. 2 - Solo"),
            ("SHOWER SOLO 🚿 POV", "Shower Solo 🚿 POV"),
            ("THE BEST DAY OF THE YEAR", "The Best Day of the Year"),
            ("Morning STRETCH", "Morning STRETCH"),
        ])

    def test_long_title_is_cut_at_a_word_with_ellipsis_within_90(self):
        self.check([(" ".join(["alpha"] * 25), " ".join(["alpha"] * 15) + "…")])

    def test_messages_and_stories_get_titles(self):
        for api_type in ("Messages", "Stories"):
            with self.subTest(api_type=api_type):
                self.assertEqual(self.title("Pool day 🌊", api_type), "Pool day 🌊")


class MentionTests(Base):
    def performers(self, text, own="examplestudio", media_id=80):
        result = self.box.scrape("Example Name (examplestudio)", own, media_id=media_id,
                                 post_id=media_id, api_type="Timeline", text=text,
                                 created_at="2001-02-03T12:00:00+00:00")
        return [p["name"] for p in result["performers"]]

    def test_mentions_become_performers(self):
        text = ('<a href="/linkeduser">@linkeduser</a> with onlyfans.com/other-user, '
                'plain @bareuser and @LinkedUser again, mail a@localhost, '
                '<a href="https://onlyfans.com/123/examplestudio">post</a> '
                '<a href="/my/chats">chat</a> @examplestudio')
        self.assertEqual(self.performers(text),
                         ["Example Name", "linkeduser", "other-user", "bareuser"])


class DiscoveryTests(Base):
    def test_falls_back_to_scanning_and_caches_hit(self):
        self.box.db("examplestudio")
        other = self.box.db("otheraccount", 2)
        filename = self.box.add_media(other, 90, 90, "Timeline", "found", "2001-02-03T12:00:00+00:00")
        path = self.box.video_path("Example Name (examplestudio)", "Timeline", filename)
        result = self.box.run(path)[0]
        self.assertEqual(result["details"], "found")
        with open(self.box.cache_path) as f:
            self.assertEqual(json.load(f), {"Example Name (examplestudio)": other})
        # cache is used even when the folder-derived DB is gone
        shutil.rmtree(os.path.dirname(self.box.db("examplestudio")))
        self.assertEqual(self.box.run(path)[0]["details"], "found")

    def test_stale_cache_entry_is_ignored_and_miss_not_cached(self):
        self.box.db("examplestudio")
        with open(self.box.cache_path, "w") as f:
            json.dump({"Example Name (examplestudio)": "/nonexistent/user_data.db"}, f)
        path = self.box.video_path("Example Name (examplestudio)", "Timeline",
                                   "2001-02-03 - x [orig_1].mp4")
        self.assertEqual(self.box.run(path)[0], {})
        with open(self.box.cache_path) as f:
            self.assertNotIn("/nonexistent/user_data.db", f.read())

    def test_root_path_with_percent_and_hash_is_readable(self):
        odd = os.path.join(self.box.tmp, "odd%41 #1")
        os.rename(self.box.root, odd)
        self.box.root = odd
        result = self.box.scrape("Example Name (examplestudio)", "examplestudio", media_id=96,
                                 post_id=96, api_type="Timeline", text="t",
                                 created_at="2001-02-03T12:00:00+00:00")
        self.assertEqual(result["details"], "t")

    def test_folder_without_username_uses_name(self):
        result = self.box.scrape("lewisxrowe", "lewisxrowe", media_id=95, post_id=95,
                                 api_type="Timeline", text="t", created_at="2001-02-03T12:00:00+00:00")
        self.assertEqual(result["studio"], {"name": "lewisxrowe"})
        self.assertEqual(result["performers"], [{"name": "lewisxrowe"}])


if __name__ == "__main__":
    unittest.main()
