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

    def __init__(self):
        self.tmp = tempfile.mkdtemp()
        self.root = os.path.join(self.tmp, "download")
        os.makedirs(os.path.join(self.root, ".data"))
        scrapers = os.path.join(self.tmp, "scrapers")
        self.scraper_dir = os.path.join(scrapers, "OFScraperUserData")
        os.makedirs(self.scraper_dir)
        shutil.copy(os.path.join(HERE, SCRIPT_NAME), self.scraper_dir)
        os.symlink(COMMUNITY, os.path.join(scrapers, "community"))
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
            "details": "<p>Hello there</p>",
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
