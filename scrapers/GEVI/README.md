# VH - Gay Erotic Video Index (GEVI)

Scrapes performers, scenes and groups from [GEVI](https://gayeroticvideoindex.com) pages by URL. A movie page fills either a scene or a group.

## Supports

- **Performer** (by URL): name, disambiguation, aliases, gender, image, hair_color, eye_color, height, weight, ethnicity, penis_length, circumcised, piercings, tattoos, birthdate, death_date, urls
- **Scene** (by URL): title, date, director, details, performers, image, urls
- **Group** (by URL): name, studio, date, duration, director, synopsis, front_image, back_image, urls

Performer URLs are `gayeroticvideoindex.com/performer/` pages. Scene and group URLs are both movie pages, `gayeroticvideoindex.com/video/`: the scene is the whole movie, not one of its scenes.

## Descriptions

A scene's details and a group's synopsis are the same Markdown built from the movie page, in sections split by `---` rules:

1. The movie description. A group's synopsis opens with a `👤` line naming the movie's cast.
2. One block per entry in the page's scene list: a bold heading with a keycap number and the scene's title, a `👤` cast line, the scene's text (scene details only, not the group synopsis) and its "See also" links. In the cast line, ⬆️ marks a top, ⬇️ a bottom and ↕️ both.
3. One `🏆` line per award.

For example, a scene's details:

```markdown
Example movie text.

---

**1️⃣ Scene 1: Example Scene**

👤 Performer A ⬆️, Performer B ⬇️

Example scene text.

See also: [Example Sequel](https://gayeroticvideoindex.com/video/2)

---

🏆 Example Award 2002: Best Example
```

The length and date GEVI appends to a scene's title (`18m 1/2/2001`) are dropped. A scene entry with nothing in it stays as a bare heading, unless another entry with the same number has content. Line starts that Markdown would read as a heading, list, quote or rule are escaped; inline markup such as `*emphasis*` is kept.

## Field notes

- **name** and **disambiguation**: a trailing part in brackets, as in `Performer B (II)`, becomes the disambiguation. Cast names in scenes and groups drop it.
- **aliases**: the "Also known as" and "Also modeled as" names, comma-separated.
- **gender**: always `MALE`.
- **hair_color**, **eye_color**, **ethnicity** and **circumcised**: GEVI's words mapped to Stash's values (`brown` hair becomes `Brunette`, `white` skin `Caucasian`, `intact` `UNCUT`). A word with no mapping is kept, upper-cased.
- **height**, **weight** and **penis_length**: the metric value only (cm, kg, cm).
- **birthdate** and **death_date**: the year only, since GEVI records no more. A circa year (`c1984`) is left out.
- **tattoos**: the locations on the first line, then one line per described tattoo.
- **date** (scene, group): the movie's release date. A circa date is left out.
- **duration**: the movie's length in minutes, as `<minutes>:00`.
- **studio**: the distributor, with its GEVI URL.
- **performers**: the movie's cast credits, each name once, with its GEVI URL.
- **image** (scene) and **front_image**: the full-size front cover. **back_image** is the back cover.

## Known limitations

- A page that cannot be fetched (an HTTP error or no answer in 10 seconds) logs an error and gives no result.
- A value GEVI gives only in imperial units (inches, pounds) is left out.

## Development

- Tests: `python3 -B -m unittest -v` from this folder. They feed made-up HTML that mirrors GEVI's page structure through a mocked `requests.get`; they never contact GEVI or Stash.
- The top/bottom markers come from GEVI's action codes (such as `OgrAtRg`): only the anal `t` and `b` flags are read. See `role_marker()`.
- `py_common` installs `requests` and `beautifulsoup4` on first run if they are missing.
