import json
import os
import re
import sys

# py_common is installed at scrapers/community/py_common/; our scraper is at
# scrapers/<vendor>/GEVI/ — go up two levels then into community/
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.realpath(__file__))), "community"))

try:
    from py_common import log
    from py_common.deps import ensure_requirements
except ModuleNotFoundError:
    print("You need to install py_common from the community scraper package.", file=sys.stderr)
    sys.exit(1)

ensure_requirements("requests", "bs4:beautifulsoup4")

import requests
from bs4 import BeautifulSoup, Comment, Tag

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


def collapse(text):
    return " ".join(text.split())


def node_text(node):
    return node.get_text() if isinstance(node, Tag) else str(node)


def escape_markdown(text):
    """Escape line starts that Markdown would read as structure (headings, quotes,
    lists, rules). Inline markup such as *emphasis* is left alone."""
    lines = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped and re.fullmatch(r"(-[ -]*|=[ =]*|_[ _]*|\*[ *]*)", stripped):
            line = "\\" + stripped
        elif match := re.match(r"(\d+)\.(\s|$)", line):
            line = f"{match.group(1)}\\." + line[match.end(1) + 1:]
        elif re.match(r"[#>+*-](\s|$)|#+(\s|$)", line):
            line = "\\" + line
        lines.append(line)
    return "\n".join(lines)


def paragraphs(box):
    """Paragraph texts, coping with the site's unclosed <p> tags nesting inside each other."""
    texts = (
        collapse("".join(
            node_text(child)
            for child in p.children
            if not isinstance(child, Comment) and not (isinstance(child, Tag) and child.name == "p")
        ))
        for p in box.find_all("p")
    )
    return "\n\n".join(escape_markdown(t) for t in texts if t)


def movie_cast_links(soup):
    """Performer links in the movie's Cast Credits box, first occurrence of each name."""
    label = soup.find("div", string=re.compile(r"^\s*Cast Credits\s*$"))
    box = label.find_next_sibling("div") if label else None
    links, seen = [], set()
    for a in box.find_all("a", href=re.compile(r"^performer/")) if box else []:
        name = strip_name_suffix(a.get_text(strip=True))
        if name and name not in seen:
            seen.add(name)
            links.append((name, a.get("href", "")))
    return links


def keycap(number):
    """Keycap emoji for a scene number, one keycap per digit (🔟 for exactly 10)."""
    if number == 10:
        return "🔟"
    return "".join(f"{digit}\ufe0f\u20e3" for digit in str(number))


def role_marker(code):
    """Top/bottom emoji from a GEVI action code such as "OgrAtRg".

    The code is a run of segments, each an upper-case act letter followed by
    lower-case flags: O oral, A anal, R rim; g/r give/receive, t/b top/bottom.
    Only the anal top/bottom flags are shown.
    """
    flags = set("".join(re.findall(r"A([a-z]*)", code))) & {"t", "b"}
    if flags == {"t", "b"}:
        return " ↕️"
    if flags == {"t"}:
        return " ⬆️"
    if flags == {"b"}:
        return " ⬇️"
    return ""


def scene_cast(row):
    """(name, action code) pairs from a scene's inline cast row."""
    cast = []
    for child in row.children:
        if isinstance(child, Tag) and child.name == "a" and child.get("href", "").startswith("performer/"):
            cast.append([strip_name_suffix(child.get_text(strip=True)), ""])
        elif cast:
            cast[-1][1] += node_text(child)
    return cast


def scene_block(scene):
    """(scene number or None, whether it has content, Markdown block) for one scenes-list entry."""
    rows = scene.find_all("div", recursive=False)
    head = rows[0] if rows else None
    label_el = head.find("span") if head else None
    label = collapse(label_el.get_text()) if label_el else ""
    header = collapse("".join(
        node_text(child) for child in head.children if child is not label_el
    )) if head else ""

    cast_row = next(
        (row for row in rows[1:] if row.find("a", href=re.compile(r"^performer/"), recursive=False)),
        None,
    )
    cast = scene_cast(cast_row) if cast_row else []

    text_box = scene.select_one(".sceneText")
    text = paragraphs(text_box) if text_box else ""

    see_also = [
        "[{}]({}/{})".format(re.sub(r"([\[\]])", r"\\\1", collapse(a.get_text())), BASE_URL, a["href"])
        for row in rows[1:]
        if collapse(row.get_text()).lower().startswith("see also")
        for a in row.find_all("a", href=re.compile(r"^video/"))
    ]

    match = re.match(r"Scene\s+(\d+)", label)
    number = int(match.group(1)) if match else None
    if number is not None:
        heading = f"{keycap(number)} Scene {number}" + (f": {header}" if header else "")
    else:
        heading = " ".join(part for part in (label, header) if part)

    parts = [f"**{heading}**"] if heading else []
    if cast:
        parts.append("👤 " + ", ".join(name + role_marker(code) for name, code in cast))
    if text:
        parts.append(text)
    if see_also:
        parts.append("See also: " + ", ".join(see_also))
    has_content = bool(header or cast or text or see_also)
    return number, has_content, "\n\n".join(parts)


def scene_blocks(soup):
    """Markdown blocks for the scenes list. An empty entry stays as a placeholder
    heading unless another entry with the same number has content."""
    scenes = [scene_block(scene) for scene in soup.select("#scenes div.scene")]
    filled = {number for number, has_content, _ in scenes if has_content and number is not None}
    return [
        block for number, has_content, block in scenes
        if block and (has_content or number is None or number not in filled)
    ]


def awards(soup):
    """🏆 lines from the Awards grid of (award, category) pairs."""
    label = soup.find("div", string=re.compile(r"^\s*Awards:\s*$"))
    grid = label.find_next_sibling("div") if label else None
    cells = [collapse(cell.get_text()) for cell in grid.find_all("div", recursive=False)] if grid else []
    lines = []
    for award, category in zip(cells[::2], cells[1::2] + [""]):
        award = escape_markdown(award)
        if award:
            lines.append(f"🏆 {award}: {category}" if category else f"🏆 {award}")
    return lines


def build_description(soup, lead=None):
    """Markdown description of a movie page; lead is an optional first section."""
    head = [lead] if lead else []
    desc_div = soup.find("div", class_="wideCols-1")
    if desc_div and (text := paragraphs(desc_div)):
        head.append(text)
    sections = ["\n\n".join(head)] if head else []
    sections += scene_blocks(soup)
    if award_lines := awards(soup):
        sections.append("\n\n".join(award_lines))
    return "\n\n---\n\n".join(sections) or None


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

    cast = [name for name, _ in movie_cast_links(soup)]
    description = build_description(soup, lead="👤 " + ", ".join(cast) if cast else None)
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

    performers = [{"name": name, "urls": [f"{BASE_URL}/{href}"]} for name, href in movie_cast_links(soup)]

    description = build_description(soup)
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
