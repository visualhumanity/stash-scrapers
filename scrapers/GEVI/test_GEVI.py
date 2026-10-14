import unittest
from unittest import mock

import GEVI

# All sample data in this file is made up. The HTML mirrors the structure of a
# GEVI movie page (/video/<id>), cut down to the parts the scraper reads.

URL = "https://gayeroticvideoindex.com/video/1"


def cast_box(names):
    rows = "".join(
        f'<div class="flex"><div class=""><a href="performer/{i}">'
        f'<span class="whitespace-nowrap">{name}</span></a></div><div></div></div>'
        for i, name in enumerate(names, 1)
    )
    return (
        '<div class="flex flex-col"><!-- cast credits -->'
        '<div class="text-yellow-300 px-2">Cast Credits</div>'
        '<div class="max-h-52"><div class="px-2 columns-1">'
        '<div class="flex"><div class="text-yellow-100">Performer</div></div>'
        f"{rows}</div></div></div>"
    )


def description_box(paragraphs):
    # GEVI leaves its <p> tags unclosed, so they nest inside each other
    body = "".join(f"<p class='mb-2'><span>{p}</span>" for p in paragraphs)
    return (
        '<div><p><span class="text-yellow-100 pr-1">Description source:</span>'
        " promotional material</p>"
        f'<div class="text-justify wideCols-1">{body}</div></div>'
    )


def scene(label, header="", cast=None, text=None, see_also=None):
    """cast: list of (name, code) pairs; text: list of paragraphs."""
    parts = [f'<div class=""><span class="text-yellow-200">{label}</span> {header}</div>']
    if cast:
        links = ", ".join(
            f'<a class="pr-1" href="performer/{9 + i}"><span class="whitespace-nowrap">{name}</span></a> {code}'
            for i, (name, code) in enumerate(cast)
        )
        parts.append(f'<div class="">{links}</div>')
    if text:
        paras = "".join(f'<p class="mb-2"><span>{t}</span></p>' for t in text)
        parts.append(
            '<div class="mr-2 flex flex-col"><div class="sceneText" wideclass="wideCols-1">'
            '<a href="episode/5"><img src="images/Episodes/episode5.jpg"/></a>'
            f"{paras}</div></div>"
        )
    if see_also:
        links = " ".join(f'<a href="video/{vid}">{title}</a>' for vid, title in see_also)
        parts.append(f"<div> see also {links}</div>")
    if text:
        parts.append('<div class="flex"> View episode at <a href="https://example.com/watch?id=5"><img/></a></div>')
    return f'<div class="scene flex-col">{"".join(parts)}</div>'


def scenes_box(blocks):
    inner = "".join(blocks) if blocks else "<span class='pl-2'>No scene information available</span>"
    return (
        '<div class="md:px-2 md:pb-2"><div class="flex space-x-2 p-2 md:px-0">'
        '<span class="text-yellow-100 pr-1">Scene source:</span> promotional material</div>'
        f'<div class="flex w-full flex-col" id="scenes">{inner}</div></div>'
    )


def awards_box(awards):
    cells = "".join(f'<div class="text-right">{a}</div><div>{c}</div>' for a, c in awards)
    return (
        '<div class="flex"><div class="text-yellow-300 pr-2">Awards:</div>'
        f'<div class="grid grid-cols-2">{cells}</div></div>'
    )


def movie_page(cast=(), description=(), scenes=None, awards=()):
    return (
        "<html><body>"
        '<h1 class="text-yellow-300">This website requires that JavaScript be enabled</h1>'
        '<div id="coverContainer"><a href="performer/99">Cover Caption Name</a></div>'
        '<section id="data"><section>'
        '<h1 class="text-yellow-300 md:text-3xl">Example Movie</h1>'
        + (cast_box(cast) if cast else "")
        + (description_box(description) if description else "")
        + (scenes_box(scenes) if scenes is not None else "")
        + (awards_box(awards) if awards else "")
        + "</section></section></body></html>"
    )


def fake_get(html):
    response = mock.Mock()
    response.text = html
    response.raise_for_status = mock.Mock()
    return mock.patch.object(GEVI.requests, "get", return_value=response)


def scrape_scene(html):
    with fake_get(html):
        return GEVI.scene_from_url(URL)


def scrape_group(html):
    with fake_get(html):
        return GEVI.group_from_url(URL)


class DescriptionOnlyTests(unittest.TestCase):
    def test_scene_details_are_the_movie_description(self):
        page = movie_page(cast=["Performer A", "Performer B"], description=["First paragraph.", "Second paragraph."])
        self.assertEqual(scrape_scene(page)["details"], "First paragraph.\n\nSecond paragraph.")

    def test_group_synopsis_starts_with_the_movie_cast(self):
        page = movie_page(cast=["Performer A", "Performer B (xx)"], description=["First paragraph."])
        self.assertEqual(
            scrape_group(page)["synopsis"],
            "👤 Performer A, Performer B\n\nFirst paragraph.",
        )

    def test_scene_performers_are_the_movie_cast(self):
        page = movie_page(cast=["Performer A", "Performer B (xx)"], description=["Text."])
        names = [p["name"] for p in scrape_scene(page)["performers"]]
        self.assertEqual(names, ["Performer A", "Performer B"])

    def test_empty_page_gives_no_description(self):
        page = movie_page()
        self.assertNotIn("details", scrape_scene(page))
        self.assertNotIn("synopsis", scrape_group(page))


class SceneBlockTests(unittest.TestCase):
    def test_scene_blocks_follow_the_description(self):
        page = movie_page(
            description=["Movie text."],
            scenes=[
                scene("Scene 1:", "Example Scene Title", text=["Scene one text."]),
                scene("Scene 2:", "21m 1/2/2001", text=["Scene two text."]),
            ],
        )
        self.assertEqual(
            scrape_scene(page)["details"],
            "Movie text.\n\n---\n\n"
            "**1️⃣ Scene 1: Example Scene Title**\n\nScene one text.\n\n---\n\n"
            "**2️⃣ Scene 2: 21m 1/2/2001**\n\nScene two text.",
        )

    def test_without_a_description_the_scenes_come_first(self):
        page = movie_page(scenes=[scene("Scene 1:", "Example Scene Title")])
        self.assertEqual(scrape_scene(page)["details"], "**1️⃣ Scene 1: Example Scene Title**")

    def test_group_keeps_the_rule_after_the_cast_line(self):
        page = movie_page(cast=["Performer A"], scenes=[scene("Scene 1:", "Example Scene Title")])
        self.assertEqual(
            scrape_group(page)["synopsis"],
            "👤 Performer A\n\n---\n\n**1️⃣ Scene 1: Example Scene Title**",
        )

    def test_empty_header_has_no_trailing_colon(self):
        page = movie_page(scenes=[scene("Scene 1:", text=["Scene text."])])
        self.assertEqual(scrape_scene(page)["details"], "**1️⃣ Scene 1**\n\nScene text.")

    def test_numbers_of_ten_and_more(self):
        blocks = [scene(f"Scene {n}:", f"Title {n}") for n in (9, 10, 12)]
        details = scrape_scene(movie_page(scenes=blocks))["details"]
        self.assertIn("**9️⃣ Scene 9: Title 9**", details)
        self.assertIn("**🔟 Scene 10: Title 10**", details)
        self.assertIn("**1️⃣2️⃣ Scene 12: Title 12**", details)

    def test_label_without_a_number_has_no_emoji(self):
        page = movie_page(scenes=[scene("Bonus:", "Example Extra")])
        self.assertEqual(scrape_scene(page)["details"], "**Bonus: Example Extra**")

    def test_no_scene_information_message_gives_no_blocks(self):
        page = movie_page(description=["Movie text."], scenes=[])
        self.assertEqual(scrape_scene(page)["details"], "Movie text.")


class SceneCastTests(unittest.TestCase):
    def details_for(self, cast, text=None):
        return scrape_scene(movie_page(scenes=[scene("Scene 1:", "Title", cast=cast, text=text)]))["details"]

    def test_cast_line_sits_between_heading_and_text(self):
        details = self.details_for([("Performer A", "OgrAt,"), ("Performer B", "OgrAbRr")], text=["Scene text."])
        self.assertEqual(
            details,
            "**1️⃣ Scene 1: Title**\n\n👤 Performer A ⬆️, Performer B ⬇️\n\nScene text.",
        )

    def test_top_and_bottom_in_one_code_is_versatile(self):
        self.assertIn("👤 Performer A ↕️, Performer B ⬇️", self.details_for([("Performer A", "Atb,"), ("Performer B", "Ab")]))

    def test_flags_in_any_order_or_separate_segments(self):
        details = self.details_for([("Performer A", "OgAbt,"), ("Performer B", "AtRgAb")])
        self.assertIn("👤 Performer A ↕️, Performer B ↕️", details)

    def test_no_anal_role_gives_no_emoji(self):
        details = self.details_for([("Performer A", "OgRr,"), ("Performer B", ","), ("Performer C", "")])
        self.assertIn("👤 Performer A, Performer B, Performer C", details)

    def test_suffix_is_stripped_before_the_emoji(self):
        self.assertIn("👤 Performer A ⬆️", self.details_for([("Performer A (xx)", "At")]))

    def test_scene_without_inline_cast_has_no_cast_line(self):
        self.assertEqual(self.details_for(None, text=["Scene text."]), "**1️⃣ Scene 1: Title**\n\nScene text.")


class SeeAlsoTests(unittest.TestCase):
    def test_see_also_links_close_the_block(self):
        page = movie_page(scenes=[
            scene("Scene 1:", "Title", cast=[("Performer A", "At")], text=["Scene text."],
                  see_also=[(2, "Other Example Movie"), (3, "Third Example Movie")]),
        ])
        self.assertEqual(
            scrape_scene(page)["details"],
            "**1️⃣ Scene 1: Title**\n\n👤 Performer A ⬆️\n\nScene text.\n\n"
            "See also: [Other Example Movie](https://gayeroticvideoindex.com/video/2), "
            "[Third Example Movie](https://gayeroticvideoindex.com/video/3)",
        )


class PlaceholderTests(unittest.TestCase):
    def test_empty_scene_stays_as_a_heading(self):
        page = movie_page(scenes=[scene("Scene 1:", "Title"), scene("Scene 2:"), scene("Scene 3:", "Title")])
        self.assertEqual(
            scrape_scene(page)["details"],
            "**1️⃣ Scene 1: Title**\n\n---\n\n**2️⃣ Scene 2**\n\n---\n\n**3️⃣ Scene 3: Title**",
        )

    def test_empty_duplicate_of_a_real_scene_is_dropped(self):
        page = movie_page(scenes=[scene("Scene 1:", "Title"), scene("Scene 2:"), scene("Scene 2:", "Real Title")])
        self.assertEqual(
            scrape_scene(page)["details"],
            "**1️⃣ Scene 1: Title**\n\n---\n\n**2️⃣ Scene 2: Real Title**",
        )


class AwardTests(unittest.TestCase):
    def test_awards_close_the_description(self):
        page = movie_page(
            description=["Movie text."],
            scenes=[scene("Scene 1:", "Title")],
            awards=[("2001 Example Award", "Best Example Video"), ("2002 Other Example Award", "")],
        )
        self.assertEqual(
            scrape_scene(page)["details"],
            "Movie text.\n\n---\n\n**1️⃣ Scene 1: Title**\n\n---\n\n"
            "🏆 2001 Example Award: Best Example Video\n\n🏆 2002 Other Example Award",
        )

    def test_awards_without_scenes_follow_the_description(self):
        page = movie_page(description=["Movie text."], awards=[("2001 Example Award", "Best Example Video")])
        self.assertEqual(
            scrape_scene(page)["details"],
            "Movie text.\n\n---\n\n🏆 2001 Example Award: Best Example Video",
        )


class EscapingTests(unittest.TestCase):
    def details_for(self, *paragraphs):
        return scrape_scene(movie_page(description=list(paragraphs)))["details"]

    def test_line_starts_that_would_become_structure_are_escaped(self):
        self.assertEqual(
            self.details_for("# Not a heading", "> Not a quote", "- Not a list", "+ Not a list", "* Not a list", "12. Not a list"),
            "\\# Not a heading\n\n\\> Not a quote\n\n\\- Not a list\n\n\\+ Not a list\n\n"
            "\\* Not a list\n\n12\\. Not a list",
        )

    def test_rule_lines_are_escaped(self):
        self.assertEqual(self.details_for("---", "==="), "\\---\n\n\\===")

    def test_inline_markup_is_left_alone(self):
        self.assertEqual(self.details_for("An *Example* with_under_scores - and 1. more"), "An *Example* with_under_scores - and 1. more")

    def test_scene_text_and_awards_are_escaped(self):
        page = movie_page(scenes=[scene("Scene 1:", text=["- Scene text"])], awards=[("# Award", "Category")])
        self.assertEqual(
            scrape_scene(page)["details"],
            "**1️⃣ Scene 1**\n\n\\- Scene text\n\n---\n\n🏆 \\# Award: Category",
        )


class ReviewFollowUpTests(unittest.TestCase):
    def full_page(self):
        return movie_page(
            cast=["Performer A", "Performer B"],
            description=["Movie text."],
            scenes=[scene("Scene 1:", "Title", cast=[("Performer A", "At"), ("Performer B", "Ab")],
                          text=["Scene text."], see_also=[(2, "Other Example Movie")])],
            awards=[("2001 Example Award", "Best Example Video")],
        )

    def test_group_differs_from_scene_only_by_the_cast_prefix(self):
        page = self.full_page()
        details = scrape_scene(page)["details"]
        self.assertEqual(scrape_group(page)["synopsis"], "👤 Performer A, Performer B\n\n" + details)
        self.assertEqual(
            details,
            "Movie text.\n\n---\n\n**1️⃣ Scene 1: Title**\n\n👤 Performer A ⬆️, Performer B ⬇️\n\n"
            "Scene text.\n\nSee also: [Other Example Movie](https://gayeroticvideoindex.com/video/2)\n\n"
            "---\n\n🏆 2001 Example Award: Best Example Video",
        )

    def test_asterisk_rule_lines_are_escaped(self):
        self.assertEqual(scrape_scene(movie_page(description=["***", "* * *"]))["details"], "\\***\n\n\\* * *")

    def test_brackets_in_see_also_titles_are_escaped(self):
        page = movie_page(scenes=[scene("Scene 1:", "Title", see_also=[(2, "Example [Uncut]")])])
        self.assertIn("[Example \\[Uncut\\]](https://gayeroticvideoindex.com/video/2)", scrape_scene(page)["details"])

    def test_entry_without_label_or_content_is_dropped(self):
        page = movie_page(scenes=['<div class="scene flex-col"><div class=""></div></div>', scene("Scene 1:", "Title")])
        self.assertEqual(scrape_scene(page)["details"], "**1️⃣ Scene 1: Title**")

    def test_unnumbered_entries_do_not_dedupe_each_other(self):
        page = movie_page(scenes=[scene("Bonus:", "Extra"), scene("Trailer:")])
        self.assertEqual(scrape_scene(page)["details"], "**Bonus: Extra**\n\n---\n\n**Trailer:**")


if __name__ == "__main__":
    unittest.main()
