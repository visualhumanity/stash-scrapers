import json
import re
import sys

from py_common import log
from py_common.deps import ensure_requirements

ensure_requirements("requests", "bs4:beautifulsoup4")

import requests
from bs4 import BeautifulSoup

HAIR_MAP = {
    "blonde": "Blonde",
    "brown": "Brunette",
    "brunette": "Brunette",
    "black": "Black",
    "red": "Red",
    "auburn": "Auburn",
    "grey": "Grey",
    "gray": "Grey",
    "bald": "Bald",
}

EYE_MAP = {
    "blue": "Blue",
    "brown": "Brown",
    "green": "Green",
    "grey": "Grey",
    "gray": "Grey",
    "hazel": "Hazel",
    "red": "Red",
}

ETHNICITY_MAP = {
    "white": "Caucasian",
    "caucasian": "Caucasian",
    "black": "Black",
    "african american": "Black",
    "asian": "Asian",
    "indian": "Indian",
    "latin": "Latin",
    "latino": "Latin",
    "hispanic": "Latin",
    "middle eastern": "Middle Eastern",
    "mixed": "Mixed",
}

CIRCUMCISED_MAP = {
    "cut": "CUT",
    "uncut": "UNCUT",
    "intact": "UNCUT",
}

BASE_URL = "https://gayeroticvideoindex.com"


def strip_name_suffix(name):
    return re.sub(r'\s*\([^)]*\)\s*$', '', name).strip()


def _build_description(performer_names, desc_div):
    parts = []
    if performer_names:
        parts.append("Performers: " + ", ".join(performer_names))
    if desc_div:
        body = "\n\n".join(p.get_text(strip=True) for p in desc_div.find_all("p") if p.get_text(strip=True))
        if body:
            parts.append(body)
    return "\n\n".join(parts) if parts else None


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


def group_from_url(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    name_el = soup.find("h1", class_="text-yellow-300")
    if name_el:
        result["name"] = name_el.get_text(strip=True)

    table = soup.find("table", class_="w-fit")
    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            cells = rows[1].find_all("td")
            if cells:
                studio_a = cells[0].find("a")
                if studio_a:
                    href = studio_a.get("href", "")
                    result["studio"] = {"name": studio_a.get_text(strip=True)}
                    if href:
                        result["studio"]["urls"] = [f"{BASE_URL}/{href}"]
            if len(cells) >= 2:
                date_text = cells[1].get_text(strip=True)
                if date_text:
                    result["date"] = date_text

    dir_label = soup.find("div", class_="text-yellow-200", string=re.compile(r"Director"))
    if dir_label:
        dir_div = dir_label.find_next_sibling("div")
        if dir_div:
            names = [a.get_text(strip=True) for a in dir_div.find_all("a")]
            if names:
                result["director"] = ", ".join(names)

    cast_div = soup.find("div", class_="columns-2")
    performers = []
    if cast_div:
        for a in cast_div.find_all("a", href=re.compile(r"^performer/")):
            name = strip_name_suffix(a.get_text(strip=True))
            if name and name not in performers:
                performers.append(name)

    desc_div = soup.find("div", class_="wideCols-1")
    description = _build_description(performers, desc_div)
    if description:
        result["synopsis"] = description

    cover_div = soup.find("div", id="coverContainer")
    if cover_div:
        imgs = [img for img in cover_div.find_all("img", class_="pictureIcon") if img.get("image")]
        if imgs:
            result["front_image"] = f"{BASE_URL}/{imgs[0]['image']}"
        if len(imgs) >= 2:
            result["back_image"] = f"{BASE_URL}/{imgs[1]['image']}"

    result["urls"] = [url]
    return result


def scene_from_url(url):
    try:
        resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
    except Exception as e:
        log.error(f"Failed to fetch {url}: {e}")
        return None

    soup = BeautifulSoup(resp.text, "html.parser")
    result = {}

    name_el = soup.find("h1", class_="text-yellow-300")
    if name_el:
        result["title"] = name_el.get_text(strip=True)

    table = soup.find("table", class_="w-fit")
    if table:
        rows = table.find_all("tr")
        if len(rows) >= 2:
            cells = rows[1].find_all("td")
            if len(cells) >= 2:
                date_text = cells[1].get_text(strip=True)
                if date_text:
                    result["date"] = date_text

    dir_label = soup.find("div", class_="text-yellow-200", string=re.compile(r"Director"))
    if dir_label:
        dir_div = dir_label.find_next_sibling("div")
        if dir_div:
            names = [a.get_text(strip=True) for a in dir_div.find_all("a")]
            if names:
                result["director"] = ", ".join(names)

    cast_div = soup.find("div", class_="columns-2")
    performers = []
    seen = set()
    if cast_div:
        for a in cast_div.find_all("a", href=re.compile(r"^performer/")):
            name = strip_name_suffix(a.get_text(strip=True))
            href = a.get("href", "")
            if name and name not in seen:
                seen.add(name)
                performers.append({"name": name, "urls": [f"{BASE_URL}/{href}"]})

    desc_div = soup.find("div", class_="wideCols-1")
    description = _build_description([p["name"] for p in performers], desc_div)
    if description:
        result["details"] = description

    if performers:
        result["performers"] = performers

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
    elif op == "group-by-url":
        url = args.get("url")
        if not url:
            log.error("No URL provided")
            print("null")
            sys.exit(0)
        result = group_from_url(url)
        print(json.dumps(result))
    elif op == "scene-by-url":
        url = args.get("url")
        if not url:
            log.error("No URL provided")
            print("null")
            sys.exit(0)
        result = scene_from_url(url)
        print(json.dumps(result))
    else:
        log.error(f"Unknown operation: {op}")
        print("null")
        sys.exit(1)
