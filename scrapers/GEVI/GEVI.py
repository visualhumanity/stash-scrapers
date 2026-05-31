import json
import re
import sys

from py_common import log
from py_common.deps import ensure_requirements

ensure_requirements("requests", "bs4:beautifulsoup4")

import requests
from bs4 import BeautifulSoup

HAIR_MAP = {
    "blonde": "BLONDE",
    "brown": "BRUNETTE",
    "brunette": "BRUNETTE",
    "black": "BLACK",
    "red": "RED",
    "auburn": "AUBURN",
    "grey": "GREY",
    "gray": "GREY",
    "bald": "BALD",
}

EYE_MAP = {
    "blue": "BLUE",
    "brown": "BROWN",
    "green": "GREEN",
    "grey": "GREY",
    "gray": "GREY",
    "hazel": "HAZEL",
    "red": "RED",
}

ETHNICITY_MAP = {
    "white": "CAUCASIAN",
    "caucasian": "CAUCASIAN",
    "black": "BLACK",
    "african american": "BLACK",
    "asian": "ASIAN",
    "indian": "INDIAN",
    "latin": "LATIN",
    "latino": "LATIN",
    "hispanic": "LATIN",
    "middle eastern": "MIDDLE_EASTERN",
    "mixed": "MIXED",
}

CIRCUMCISED_MAP = {
    "cut": "CUT",
    "uncut": "UNCUT",
    "intact": "UNCUT",
}


def get_stat(stats_container, label):
    for flex_div in stats_container.find_all("div", class_="flex"):
        label_el = flex_div.find("div", class_="text-yellow-100")
        if label_el and label_el.get_text(strip=True) == label:
            value_el = label_el.find_next_sibling("div")
            if value_el:
                return value_el.get_text(separator="\n", strip=True).split("\n")[0]
    return None


def performer_from_url(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    name_el = soup.find("h1", class_="text-yellow-200")
    if name_el:
        result["name"] = name_el.get_text(strip=True)

    aliases = []
    for label_text, tag in (("Also known as", "h2"), ("Also modeled as", "h3")):
        label_div = soup.find("div", string=lambda t, lt=label_text: t and lt in t)
        if label_div:
            parent = label_div.parent
            aliases.extend(
                el.get_text(strip=True)
                for el in parent.find_all(tag, class_="text-yellow-200")
            )
    if aliases:
        result["aliases"] = ", ".join(aliases)

    stats = soup.find("div", class_="border border-gray-400 px-2")
    if stats:
        hair_raw = get_stat(stats, "Hair:")
        if hair_raw:
            result["hair_color"] = HAIR_MAP.get(hair_raw.lower(), hair_raw.upper())

        eyes_raw = get_stat(stats, "Eyes:")
        if eyes_raw:
            result["eye_color"] = EYE_MAP.get(eyes_raw.lower(), eyes_raw.upper())

        height_raw = get_stat(stats, "Height:")
        if height_raw:
            m = re.search(r"(\d+)\s*cm", height_raw, re.I)
            if m:
                result["height"] = m.group(1)

        weight_raw = get_stat(stats, "Weight:")
        if weight_raw:
            m = re.search(r"(\d+)\s*kg", weight_raw, re.I)
            if m:
                result["weight"] = m.group(1)

        skin_raw = get_stat(stats, "Skin:")
        if skin_raw:
            result["ethnicity"] = ETHNICITY_MAP.get(skin_raw.lower(), skin_raw.upper())

        dick_raw = get_stat(stats, "Dick Size:")
        if dick_raw:
            m = re.search(r"([\d.]+)\s*cm", dick_raw, re.I)
            if m:
                result["penis_length"] = m.group(1)

        foreskin_raw = get_stat(stats, "Foreskin:")
        if foreskin_raw:
            result["circumcised"] = CIRCUMCISED_MAP.get(foreskin_raw.lower(), foreskin_raw.upper())

        born_raw = get_stat(stats, "Born:")
        if born_raw:
            result["birthdate"] = born_raw.strip()

    result["gender"] = "MALE"
    result["urls"] = [url]

    return result


if __name__ == "__main__":
    from py_common.util import scraper_args

    op, args = scraper_args()
    if op == "performer-by-url":
        url = args.get("url")
        if not url:
            log.error("No URL provided")
            print("null")
            sys.exit(0)
        result = performer_from_url(url)
        print(json.dumps(result))
    else:
        log.error(f"Unknown operation: {op}")
        print("null")
        sys.exit(1)
