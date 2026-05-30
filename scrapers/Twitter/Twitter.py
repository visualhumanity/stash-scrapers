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

deps.ensure_requirements("requests")
import requests

TWITTER_API_BASE = "https://api.twitter.com/2"
USER_FIELDS = "name,description,profile_image_url"


def get_bearer_token():
    token = os.environ.get("TWITTER_BEARER_TOKEN")
    if not token:
        log.error("TWITTER_BEARER_TOKEN environment variable is not set")
    return token


def fetch_user(handle, token):
    url = f"{TWITTER_API_BASE}/users/by/username/{handle}"
    try:
        resp = requests.get(
            url,
            params={"user.fields": USER_FIELDS},
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 404:
            log.info(f"Twitter user not found: @{handle}")
            return None
        if resp.status_code == 401:
            log.error("Twitter bearer token is invalid or expired")
            return None
        resp.raise_for_status()
        data = resp.json().get("data")
        if not data:
            log.info(f"No data returned for Twitter user: @{handle}")
        return data
    except requests.RequestException as e:
        log.error(f"Twitter API request failed: {e}")
        return None


def extract_handle(url):
    m = re.search(r'(?:twitter\.com|x\.com)/([A-Za-z0-9_]+)', url)
    return m.group(1) if m else None


def profile_url(username):
    return f"https://twitter.com/{username}"


def performer_by_url(url):
    handle = extract_handle(url)
    if not handle:
        log.error(f"Could not extract handle from URL: {url}")
        print("null")
        sys.exit(0)

    token = get_bearer_token()
    if not token:
        print("null")
        sys.exit(0)

    data = fetch_user(handle, token)
    if not data:
        print("null")
        sys.exit(0)

    image = data.get("profile_image_url", "").replace("_normal.", "_400x400.")
    result = {
        "Name": data.get("name"),
        "URLs": [profile_url(data["username"])],
        "Twitter": profile_url(data["username"]),
        "Details": data.get("description") or None,
        "Image": image or None,
    }
    print(json.dumps({k: v for k, v in result.items() if v}))


def performer_by_name(query):
    handle = query.strip().lstrip("@").strip()
    if not handle:
        print(json.dumps([]))
        sys.exit(0)

    token = get_bearer_token()
    if not token:
        print("null")
        sys.exit(0)

    data = fetch_user(handle, token)
    if not data:
        print(json.dumps([]))
        sys.exit(0)

    result = {
        "Name": data.get("name"),
        "URLs": [profile_url(data["username"])],
    }
    print(json.dumps([{k: v for k, v in result.items() if v}]))


if __name__ == "__main__":
    if len(sys.argv) < 2:
        log.error("No operation specified")
        print("null")
        sys.exit(1)

    op = sys.argv[1]
    fragment = json.loads(sys.stdin.read())

    if op == "performer-by-url":
        url = fragment.get("url")
        if not url:
            log.error("No URL in fragment")
            print("null")
            sys.exit(0)
        performer_by_url(url)
    elif op == "performer-by-name":
        name = fragment.get("name", "")
        performer_by_name(name)
    else:
        log.error(f"Unknown operation: {op}")
        print("null")
        sys.exit(1)
