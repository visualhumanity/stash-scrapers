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


def release_table(released, length):
    return (
        '<table class="w-fit"><tr class="text-yellow-100"><th>Distributor</th><th>Released</th><th>Length</th></tr>'
        f'<tr><td><a href="company/7">Example Studio</a> </td><td>{released}</td><td>{length}</td></tr></table>'
    )


def movie_page(cast=(), description=(), scenes=None, awards=(), released="2001", length="90", covers=()):
    return (
        "<html><body>"
        '<div id="jsrequired"><h1 class="text-center text-3xl text-yellow-300">'
        "This website requires that JavaScript be enabled in order to display\n properly.</h1></div>"
        '<section id="warning"><h1 class="text-2xl font-bold text-yellow-300">Site Name</h1></section>'
        '<h2 class="text-center text-2xl uppercase md:block md:text-3xl">Site Heading</h2>'
        '<div id="coverContainer"><a href="performer/99">Cover Caption Name</a>'
        + "".join(
            f"<img src='images/Covers/Icons/1/{name}' alt class='pictureIcon h-[184px]' "
            f"image='images/Covers/1/{name}'subtitle=\"\" />"
            for name in covers
        )
        + "</div>"
        '<section id="data"><section>'
        '<h1 class="text-center text-2xl text-yellow-300 md:text-start md:text-3xl">\n  Example Movie  </h1>'
        + release_table(released, length)
        + (cast_box(cast) if cast else "")
        + (description_box(description) if description else "")
        + (scenes_box(scenes) if scenes is not None else "")
        + (awards_box(awards) if awards else "")
        + "</section></section></body></html>"
    )


def performer_page(name="Performer A", image=None, stats=(), tattoos=None):
    """stats: (label, value-HTML) pairs; tattoos: (locations, [(place, description)])."""
    rows = "".join(
        f'<div class="flex items-start space-x-1"><div class="text-yellow-100 whitespace-nowrap">{label}</div>'
        f"<div class='whitespace-nowrap'>{value}</div></div>"
        for label, value in stats
    )
    tattoo_html = ""
    if tattoos:
        locations, details = tattoos
        notes = "".join(f"<b>{place}:</b> {text}<br/>" for place, text in details)
        tattoo_html = (
            '<div><span class="text-yellow-100">Tattoos:&nbsp;</span>'
            f"\n   {locations}<br />" + (f'<span style="">{notes}</span>' if notes else "") + " </div>"
        )
    return (
        "<html><body>"
        '<div id="jsrequired"><h1 class="text-center text-3xl text-yellow-300">JavaScript notice</h1></div>'
        f'<h1 class="text-3xl text-yellow-200">{name}</h1>'
        + (f"<img src='{image}' />" if image else "")
        + f'<div class="border border-gray-400 px-2"><div class="columns-2">{rows}</div>{tattoo_html}</div>'
        "</body></html>"
    )


def scrape_performer(html):
    with fake_get(html):
        return GEVI.performer_from_url("https://gayeroticvideoindex.com/performer/1")


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
            "**2️⃣ Scene 2**\n\nScene two text.",
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

    def test_scene_details_include_the_scene_text(self):
        self.assertEqual(
            scrape_scene(self.full_page())["details"],
            "Movie text.\n\n---\n\n**1️⃣ Scene 1: Title**\n\n👤 Performer A ⬆️, Performer B ⬇️\n\n"
            "Scene text.\n\nSee also: [Other Example Movie](https://gayeroticvideoindex.com/video/2)\n\n"
            "---\n\n🏆 2001 Example Award: Best Example Video",
        )

    def test_group_synopsis_leaves_out_the_scene_text(self):
        self.assertEqual(
            scrape_group(self.full_page())["synopsis"],
            "👤 Performer A, Performer B\n\nMovie text.\n\n---\n\n"
            "**1️⃣ Scene 1: Title**\n\n👤 Performer A ⬆️, Performer B ⬇️\n\n"
            "See also: [Other Example Movie](https://gayeroticvideoindex.com/video/2)\n\n"
            "---\n\n🏆 2001 Example Award: Best Example Video",
        )

    def test_group_keeps_a_text_only_scene_over_its_empty_duplicate(self):
        page = movie_page(scenes=[scene("Scene 1:"), scene("Scene 1:", text=["Scene text."])])
        self.assertEqual(scrape_group(page)["synopsis"], "**1️⃣ Scene 1**")

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


class TitleTests(unittest.TestCase):
    def test_scene_title_skips_the_hidden_banners(self):
        self.assertEqual(scrape_scene(movie_page())["title"], "Example Movie")

    def test_group_name_skips_the_hidden_banners(self):
        self.assertEqual(scrape_group(movie_page())["name"], "Example Movie")


class SceneHeaderTests(unittest.TestCase):
    def heading_for(self, header):
        return scrape_scene(movie_page(scenes=[scene("Scene 1:", header)]))["details"]

    def test_length_and_date_are_dropped_from_the_title(self):
        self.assertEqual(self.heading_for("Example Title 18m 1/2/2001"), "**1️⃣ Scene 1: Example Title**")

    def test_length_or_date_alone_is_dropped(self):
        self.assertEqual(self.heading_for("Example Title 18m"), "**1️⃣ Scene 1: Example Title**")
        self.assertEqual(self.heading_for("Example Title 12/31/2001"), "**1️⃣ Scene 1: Example Title**")

    def test_header_of_only_length_and_date_leaves_a_bare_heading(self):
        self.assertEqual(self.heading_for("21m 1/2/2001"), "**1️⃣ Scene 1**")

    def test_circa_years_are_dropped(self):
        self.assertEqual(self.heading_for("Example Title 18m c2001"), "**1️⃣ Scene 1: Example Title**")
        self.assertEqual(self.heading_for("Example Title c2001"), "**1️⃣ Scene 1: Example Title**")

    def test_hour_lengths_are_dropped(self):
        self.assertEqual(self.heading_for("Example Title 1h 5m 1/2/2001"), "**1️⃣ Scene 1: Example Title**")

    def test_numbers_inside_the_title_are_kept(self):
        self.assertEqual(self.heading_for("Example Title 2 21m"), "**1️⃣ Scene 1: Example Title 2**")
        self.assertEqual(self.heading_for("Room 18m Down"), "**1️⃣ Scene 1: Room 18m Down**")

    def test_scene_with_only_length_and_date_still_counts_as_filled(self):
        page = movie_page(scenes=[scene("Scene 1:"), scene("Scene 1:", "21m 1/2/2001")])
        self.assertEqual(scrape_scene(page)["details"], "**1️⃣ Scene 1**")


class ReleaseTableTests(unittest.TestCase):
    def test_group_gets_studio_date_and_duration(self):
        group = scrape_group(movie_page(released="2001", length="103"))
        self.assertEqual(group["studio"]["name"], "Example Studio")
        self.assertEqual(group["date"], "2001")
        self.assertEqual(group["duration"], "103:00")

    def test_unknown_length_gives_no_duration(self):
        self.assertNotIn("duration", scrape_group(movie_page(length="?")))
        self.assertNotIn("duration", scrape_group(movie_page(length="")))

    def test_circa_release_date_is_omitted(self):
        self.assertNotIn("date", scrape_group(movie_page(released="c2001")))
        self.assertNotIn("date", scrape_scene(movie_page(released="c2001")))

    def test_scene_gets_the_release_date(self):
        self.assertEqual(scrape_scene(movie_page(released="2001"))["date"], "2001")


class PerformerTests(unittest.TestCase):
    def test_disambiguation_is_split_off_the_name(self):
        performer = scrape_performer(performer_page(name="Performer A (xx)"))
        self.assertEqual((performer["name"], performer["disambiguation"]), ("Performer A", "xx"))

    def test_plain_name_has_no_disambiguation(self):
        performer = scrape_performer(performer_page(name="Performer A"))
        self.assertEqual(performer["name"], "Performer A")
        self.assertNotIn("disambiguation", performer)

    def test_image_is_made_absolute(self):
        performer = scrape_performer(performer_page(image="images/Stars/performer1.jpg"))
        self.assertEqual(performer["image"], "https://gayeroticvideoindex.com/images/Stars/performer1.jpg")

    def test_no_photo_gives_no_image(self):
        self.assertNotIn("image", scrape_performer(performer_page()))

    def test_piercings(self):
        self.assertEqual(scrape_performer(performer_page(stats=[("Piercing:", "Ear")]))["piercings"], "Ear")
        self.assertEqual(
            scrape_performer(performer_page(stats=[("Piercing:", "Ear<br/>Nipple")]))["piercings"], "Ear, Nipple"
        )

    def test_tattoo_locations(self):
        performer = scrape_performer(performer_page(tattoos=("Wrist, Back", [])))
        self.assertEqual(performer["tattoos"], "Wrist, Back")

    def test_tattoo_locations_with_descriptions(self):
        performer = scrape_performer(performer_page(
            tattoos=("Wrist, Back", [("left wrist", "example star"), ("back", "example text")])
        ))
        self.assertEqual(performer["tattoos"], "Wrist, Back\nleft wrist: example star\nback: example text")

    def test_no_tattoos(self):
        self.assertNotIn("tattoos", scrape_performer(performer_page()))

    def test_born_and_died_years(self):
        performer = scrape_performer(performer_page(stats=[("Born:", "1981"), ("Died:", "2023")]))
        self.assertEqual((performer["birthdate"], performer["death_date"]), ("1981", "2023"))

    def test_circa_born_and_died_are_omitted(self):
        performer = scrape_performer(performer_page(stats=[("Born:", "c1984"), ("Died:", "c2020")]))
        self.assertNotIn("birthdate", performer)
        self.assertNotIn("death_date", performer)


class NoneValueTests(unittest.TestCase):
    def test_none_is_dropped_from_piercings(self):
        performer = scrape_performer(performer_page(stats=[("Piercing:", "None<br/>Nose")]))
        self.assertEqual(performer["piercings"], "Nose")

    def test_empty_piercing_value_gives_no_piercings(self):
        self.assertNotIn("piercings", scrape_performer(performer_page(stats=[("Piercing:", "")])))

    def test_only_none_gives_no_piercings(self):
        self.assertNotIn("piercings", scrape_performer(performer_page(stats=[("Piercing:", "None")])))

    def test_none_is_dropped_from_tattoo_locations(self):
        performer = scrape_performer(performer_page(tattoos=("None, Forearm", [("left forearm", "example word")])))
        self.assertEqual(performer["tattoos"], "Forearm\nleft forearm: example word")

    def test_only_none_gives_no_tattoos(self):
        self.assertNotIn("tattoos", scrape_performer(performer_page(tattoos=("None", []))))


class CoverTests(unittest.TestCase):
    def test_scene_image_is_the_full_size_front_cover(self):
        scene_result = scrape_scene(movie_page(covers=["video1.jpg", "video1b.jpg"]))
        self.assertEqual(scene_result["image"], "https://gayeroticvideoindex.com/images/Covers/1/video1.jpg")

    def test_group_gets_front_and_back_covers(self):
        group = scrape_group(movie_page(covers=["video1.jpg", "video1b.jpg"]))
        self.assertEqual(group["front_image"], "https://gayeroticvideoindex.com/images/Covers/1/video1.jpg")
        self.assertEqual(group["back_image"], "https://gayeroticvideoindex.com/images/Covers/1/video1b.jpg")

    def test_no_covers_gives_no_image(self):
        self.assertNotIn("image", scrape_scene(movie_page()))
        self.assertNotIn("front_image", scrape_group(movie_page()))


if __name__ == "__main__":
    unittest.main()
