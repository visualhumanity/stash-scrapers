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


# Trailing "<length> <date>" that GEVI appends to a scene header, either part optional:
# "Example Title 18m 1/2/2001", "21m 1/2/2001", "Example Title 1h 5m", "Example Title c2001".
_SCENE_DATE = r"(?:\d{1,2}/\d{1,2}/\d{4}|c\d{4})"
SCENE_LENGTH_DATE = re.compile(
    rf"(?:^|\s+)(?:(?:\d+h(?:\s*\d+m)?|\d+m)(?:\s+{_SCENE_DATE})?|{_SCENE_DATE})$"
)


def scene_block(scene, include_text=True):
    """(scene number or None, whether it has content, Markdown block) for one scenes-list entry.
    The scene text counts as content even when include_text leaves it out of the block."""
    rows = scene.find_all("div", recursive=False)
    head = rows[0] if rows else None
    label_el = head.find("span") if head else None
    label = collapse(label_el.get_text()) if label_el else ""
    raw_header = collapse("".join(
        node_text(child) for child in head.children if child is not label_el
    )) if head else ""
    header = SCENE_LENGTH_DATE.sub("", raw_header)

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
    if text and include_text:
        parts.append(text)
    if see_also:
        parts.append("See also: " + ", ".join(see_also))
    has_content = bool(raw_header or cast or text or see_also)
    return number, has_content, "\n\n".join(parts)


def scene_blocks(soup, include_text=True):
    """Markdown blocks for the scenes list. An empty entry stays as a placeholder
    heading unless another entry with the same number has content."""
    scenes = [scene_block(scene, include_text) for scene in soup.select("#scenes div.scene")]
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


def build_description(soup, lead=None, scene_text=True):
    """Markdown description of a movie page; lead is an optional first section,
    scene_text whether scene blocks carry each scene's description."""
    head = [lead] if lead else []
    desc_div = soup.find("div", class_="wideCols-1")
    if desc_div and (text := paragraphs(desc_div)):
        head.append(text)
    sections = ["\n\n".join(head)] if head else []
    sections += scene_blocks(soup, scene_text)
    if award_lines := awards(soup):
        sections.append("\n\n".join(award_lines))
    return "\n\n---\n\n".join(sections) or None


def exact_date(text):
    """A GEVI date, or None for an empty or circa ("c2001") value."""
    text = (text or "").strip()
    return text if text and not text.lower().startswith("c") else None


def release_info(soup):
    """{column header: cell} for the movie's Distributor / Released / Length table."""
    table = soup.find("table", class_="w-fit")
    rows = table.find_all("tr") if table else []
    if len(rows) < 2:
        return {}
    headers = [collapse(th.get_text()) for th in rows[0].find_all(["th", "td"])]
    return dict(zip(headers, rows[1].find_all("td")))


def movie_title(soup):
    """The movie's title heading. Earlier h1s on the page are hidden banners
    (the JavaScript notice and the age warning)."""
    title = soup.find("h1", class_="md:text-3xl")
    return collapse(title.get_text()) if title else None


def get_stat_values(stats_container, label):
    """All lines of a stat's value (GEVI separates multiple values with <br>)."""
    for flex_div in stats_container.find_all("div", class_="flex"):
        label_el = flex_div.find("div", class_="text-yellow-100")
        if label_el and label_el.get_text(strip=True) == label:
            value_el = label_el.find_next_sibling("div")
            if value_el:
                return value_el.get_text(separator="\n", strip=True).split("\n")
    return []


def get_stat(stats_container, label):
    values = get_stat_values(stats_container, label)
    return values[0] if values else None


def tattoos(soup):
    """Tattoo locations, then one line per described tattoo:
    "Tattoos: <locations><br><span><b>place:</b> description<br>...</span>"."""
    label = soup.find("span", string=re.compile(r"^\s*Tattoos:"))
    if not label:
        return None
    parts = []

    def walk(node):
        for child in node.children:
            if child is label or isinstance(child, Comment):
                continue
            if isinstance(child, Tag):
                if child.name == "br":
                    parts.append("\n")
                else:
                    walk(child)
            else:
                parts.append(str(child))

    walk(label.parent)
    lines = [collapse(line) for line in "".join(parts).split("\n")]
    lines = [line for line in lines if line]
    if lines:
        # GEVI keeps "None" next to tattoos added later ("None, Forearm")
        lines[0] = ", ".join(place for place in lines[0].split(", ") if place.lower() != "none")
    return "\n".join(line for line in lines if line) or None


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
        name = collapse(name_el.get_text())
        match = re.fullmatch(r"(.*?)\s*\(([^)]*)\)", name)
        if match and match.group(1):
            result["name"], result["disambiguation"] = match.group(1), match.group(2)
        else:
            result["name"] = name

    image = soup.find("img", src=re.compile(r"Stars"))
    if image:
        src = image["src"]
        result["image"] = src if src.startswith("http") else f"{BASE_URL}/{src.lstrip('/')}"

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

        piercings = [p for p in get_stat_values(stats, "Piercing:") if p.lower() != "none"]
        if piercings:
            result["piercings"] = ", ".join(piercings)

        # GEVI only records years; "c1984" is a guess, so it is left out
        for label, field in (("Born:", "birthdate"), ("Died:", "death_date")):
            year = exact_date(get_stat(stats, label))
            if year:
                result[field] = year[-4:]

        tattoo_text = tattoos(stats)
        if tattoo_text:
            result["tattoos"] = tattoo_text

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

    if title := movie_title(soup):
        result["name"] = title

    release = release_info(soup)
    studio_a = release["Distributor"].find("a") if "Distributor" in release else None
    if studio_a:
        href = studio_a.get("href", "")
        result["studio"] = {"name": studio_a.get_text(strip=True)}
        if href:
            result["studio"]["urls"] = [f"{BASE_URL}/{href}"]
    if "Released" in release and (date := exact_date(release["Released"].get_text())):
        result["date"] = date
    if "Length" in release and (minutes := release["Length"].get_text(strip=True)).isdigit():
        result["duration"] = f"{minutes}:00"

    dir_label = soup.find("div", class_="text-yellow-200", string=re.compile(r"Director"))
    if dir_label:
        dir_div = dir_label.find_next_sibling("div")
        if dir_div:
            names = [a.get_text(strip=True) for a in dir_div.find_all("a")]
            if names:
                result["director"] = ", ".join(names)

    cast = [name for name, _ in movie_cast_links(soup)]
    description = build_description(soup, lead="👤 " + ", ".join(cast) if cast else None, scene_text=False)
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

    if title := movie_title(soup):
        result["title"] = title

    release = release_info(soup)
    if "Released" in release and (date := exact_date(release["Released"].get_text())):
        result["date"] = date

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
