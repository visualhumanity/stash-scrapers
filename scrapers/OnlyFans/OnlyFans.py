import http.cookiejar
import json
import os
import re
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log, deps
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

deps.ensure_requirements("requests", "lxml")
import requests
from lxml import html

SCRAPER_DIR = os.path.dirname(os.path.realpath(__file__))
COOKIES_FILE = os.path.join(SCRAPER_DIR, "OnlyFans.cookies")

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# OF usernames that are internal site paths, not creator accounts
_OF_INTERNAL_PATHS = {
    "home", "login", "signup", "settings", "messages", "notifications",
    "search", "referral", "my", "bundles", "cart", "privacy",
    "terms", "dmca", "help", "contact",
}


def extract_username(url):
    m = re.search(r'onlyfans\.com/([^/?#]+)', url)
    if not m:
        return None
    username = m.group(1).lower()
    return None if username in _OF_INTERNAL_PATHS else m.group(1)


def load_cookies():
    if not os.path.exists(COOKIES_FILE):
        return None
    jar = http.cookiejar.MozillaCookieJar(COOKIES_FILE)
    try:
        jar.load(ignore_discard=True, ignore_expires=True)
        return jar
    except Exception as e:
        log.warning(f"Could not load {COOKIES_FILE}: {e}")
        return None


def make_session(cookies=None):
    session = requests.Session()
    session.headers.update({"User-Agent": BROWSER_UA})
    if cookies:
        session.cookies = cookies
    return session


def fetch_page(username, session):
    url = f"https://onlyfans.com/{username}"
    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        return resp.text
    except requests.HTTPError as e:
        log.error(f"HTTP error fetching OnlyFans profile for '{username}': {e}")
        return None
    except requests.RequestException as e:
        log.error(f"Request failed for OnlyFans profile '{username}': {e}")
        return None


def parse_profile(page_html):
    tree = html.fromstring(page_html)

    # Primary: Next.js SSR state embedded in the page
    next_data_nodes = tree.xpath('//script[@id="__NEXT_DATA__"]/text()')
    if next_data_nodes:
        try:
            data = json.loads(next_data_nodes[0])
            profile = (
                data.get("props", {})
                    .get("pageProps", {})
                    .get("profileData") or {}
            )
            if profile:
                return {
                    "name": profile.get("name") or None,
                    "bio": profile.get("rawAbout") or profile.get("about") or None,
                    "avatar": profile.get("avatar") or None,
                    "header": profile.get("header") or None,
                }
        except (json.JSONDecodeError, AttributeError):
            pass

    # Fallback: OpenGraph meta tags
    def og(prop):
        vals = tree.xpath(f'//meta[@property="og:{prop}"]/@content')
        v = vals[0].strip() if vals else None
        return v or None

    return {
        "name": og("title"),
        "bio": og("description"),
        "avatar": og("image"),
        "header": None,
    }


def get_stash_version():
    try:
        from py_common import graphql
        result = graphql.callGraphQL("{ version { version } }")
        return (result or {}).get("version", {}).get("version", "")
    except Exception:
        return ""


def is_old_stash():
    m = re.match(r'v?(\d+)\.(\d+)\.(\d+)', get_stash_version())
    if not m:
        return False  # unknown → treat as new Stash
    return (int(m[1]), int(m[2]), int(m[3])) <= (0, 30, 0)


def performer_by_url(url):
    username = extract_username(url)
    if not username:
        log.error(f"Could not extract OnlyFans username from URL: {url}")
        print("null")
        sys.exit(0)

    cookies = load_cookies()
    if not cookies:
        log.info("No OnlyFans.cookies file found — fetching public profile data only")
    session = make_session(cookies)

    page = fetch_page(username, session)
    if not page:
        print("null")
        sys.exit(0)

    profile = parse_profile(page)
    canonical_url = f"https://onlyfans.com/{username}"

    result = {
        "Name": profile["name"],
        "Details": profile["bio"],
        "Image": profile["avatar"],
        "URLs": [canonical_url],
    }
    print(json.dumps({k: v for k, v in result.items() if v}))


def studio_by_url(url):
    username = extract_username(url)
    if not username:
        log.error(f"Could not extract OnlyFans username from URL: {url}")
        print("null")
        sys.exit(0)

    cookies = load_cookies()
    if not cookies:
        log.info("No OnlyFans.cookies file found — header image requires an authenticated session")
    session = make_session(cookies)

    page = fetch_page(username, session)
    if not page:
        print("null")
        sys.exit(0)

    profile = parse_profile(page)
    canonical_url = f"https://onlyfans.com/{username}"

    image = profile["header"] or profile["avatar"]
    if not profile["header"] and profile["avatar"]:
        log.info("Header image not found; using avatar as studio image")

    if is_old_stash():
        result = {
            "Name": profile["name"],
            "Details": profile["bio"],
            "Image": image,
            "URL": canonical_url,
        }
    else:
        result = {
            "Name": profile["name"],
            "Details": profile["bio"],
            "Image": image,
            "URLs": [canonical_url],
        }
    print(json.dumps({k: v for k, v in result.items() if v}))


if __name__ == "__main__":
    op = sys.argv[1] if len(sys.argv) > 1 else ""
    fragment = json.loads(sys.stdin.read())
    url = fragment.get("url", "")

    if not url:
        log.error("No URL provided in fragment")
        print("null")
        sys.exit(0)

    if op == "performer-by-url":
        performer_by_url(url)
    elif op == "studio-by-url":
        studio_by_url(url)
    else:
        log.error(f"Unknown operation: {op}")
        print("null")
        sys.exit(1)
