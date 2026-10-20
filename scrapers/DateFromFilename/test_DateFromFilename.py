import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from DateFromFilename import parse_date

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "DateFromFilename.py")

# All sample filenames in this file are made up


class ExistingNumericFormatTests(unittest.TestCase):
    def test_year_first(self):
        self.assertEqual(parse_date("clip 2024-05-17"), "2024-05-17")
        self.assertEqual(parse_date("clip_2024.5.7"), "2024-05-07")

    def test_year_first_with_day_in_the_middle(self):
        self.assertEqual(parse_date("clip 2024_17_05"), "2024-05-17")

    def test_year_last(self):
        self.assertEqual(parse_date("clip 17-05-2024"), "2024-05-17")
        self.assertEqual(parse_date("clip 05.17.2024"), "2024-05-17")

    def test_eight_digits(self):
        self.assertEqual(parse_date("clip 20240517"), "2024-05-17")
        self.assertEqual(parse_date("clip 17052024"), "2024-05-17")
        self.assertEqual(parse_date("clip 05172024"), "2024-05-17")

    def test_ambiguous_year_last_gives_nothing(self):
        self.assertIsNone(parse_date("clip 05-06-2024"))
        self.assertIsNone(parse_date("clip 05062024"))

    def test_mixed_separators_give_nothing(self):
        self.assertIsNone(parse_date("clip 2024-05_17"))

    def test_spaces_are_not_numeric_separators(self):
        self.assertIsNone(parse_date("clip 2024 05 17"))

    def test_digits_touching_the_date_give_nothing(self):
        self.assertIsNone(parse_date("clip 12024-05-17"))

    def test_letters_touching_the_date_are_fine(self):
        self.assertEqual(parse_date("clip2024-05-17"), "2024-05-17")

    def test_invalid_calendar_date_gives_nothing(self):
        self.assertIsNone(parse_date("clip 2024-02-30"))

    def test_year_out_of_range_gives_nothing(self):
        self.assertIsNone(parse_date("clip 1850-05-17"))


class MonthNameTests(unittest.TestCase):
    def test_month_day_year(self):
        self.assertEqual(parse_date("clip Feb 16 2025"), "2025-02-16")

    def test_full_month_name(self):
        self.assertEqual(parse_date("clip February 16 2025"), "2025-02-16")

    def test_abbreviation_dot_and_comma_after_day(self):
        self.assertEqual(parse_date("clip Feb. 16, 2025"), "2025-02-16")

    def test_full_name_takes_no_dot(self):
        self.assertIsNone(parse_date("clip February. 16 2025"))

    def test_any_letter_case(self):
        self.assertEqual(parse_date("clip FEB 16 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip feb 16 2025"), "2025-02-16")

    def test_september_variants(self):
        self.assertEqual(parse_date("clip Sep 16 2025"), "2025-09-16")
        self.assertEqual(parse_date("clip Sept. 16 2025"), "2025-09-16")
        self.assertEqual(parse_date("clip September 16 2025"), "2025-09-16")

    def test_consistent_separator(self):
        self.assertEqual(parse_date("clip Feb-16-2025"), "2025-02-16")
        self.assertEqual(parse_date("clip Feb_16_2025"), "2025-02-16")
        self.assertEqual(parse_date("clip Feb.16.2025"), "2025-02-16")
        self.assertIsNone(parse_date("clip Feb-16_2025"))
        self.assertIsNone(parse_date("clip Feb - 16 - 2025"))

    def test_month_word_inside_another_word(self):
        self.assertIsNone(parse_date("Marvel 16 2025"))
        self.assertIsNone(parse_date("Junior 16 2025"))
        self.assertIsNone(parse_date("Decent 16 2025"))

    def test_may_is_a_month_like_any_other(self):
        self.assertEqual(parse_date("clip May 16 2025"), "2025-05-16")

    def test_weekday_prefix_does_not_block(self):
        self.assertEqual(parse_date("Sun Feb 16 2025"), "2025-02-16")
        self.assertEqual(parse_date("Sunday, February 16, 2025"), "2025-02-16")

    def test_invalid_day_gives_nothing(self):
        self.assertIsNone(parse_date("clip Feb 30 2025"))

    def test_day_month_year(self):
        self.assertEqual(parse_date("clip 16 Feb 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16-Feb-2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16.Feb.2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16 February 2025"), "2025-02-16")

    def test_year_month_day(self):
        self.assertEqual(parse_date("clip 2025 Feb 16"), "2025-02-16")
        self.assertEqual(parse_date("clip 2025-Feb-16"), "2025-02-16")

    def test_english_ordinals(self):
        self.assertEqual(parse_date("clip Feb 16th 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip February 1st, 2025"), "2025-02-01")
        self.assertEqual(parse_date("clip 16th of February 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 2nd Feb 2025"), "2025-02-02")


class PartialAndShortYearTests(unittest.TestCase):
    def test_month_and_year(self):
        self.assertEqual(parse_date("clip Feb 2025"), "2025-02")
        self.assertEqual(parse_date("clip February 2025"), "2025-02")
        self.assertEqual(parse_date("clip febrero de 2025"), "2025-02")
        self.assertEqual(parse_date("clip May 2025"), "2025-05")

    def test_two_digit_year_with_a_day(self):
        self.assertEqual(parse_date("clip 16 Feb 25"), "2025-02-16")
        self.assertEqual(parse_date("clip Feb 16, '25"), "2025-02-16")
        self.assertEqual(parse_date("clip Feb 16 25"), "2025-02-16")

    def test_two_digit_year_without_a_day_needs_an_apostrophe(self):
        self.assertEqual(parse_date("clip Feb '25"), "2025-02")
        self.assertIsNone(parse_date("clip Feb 25"))

    def test_two_digit_year_must_stand_alone(self):
        self.assertIsNone(parse_date("clip Feb 16 25min"))

    def test_compact_day_month_year(self):
        self.assertEqual(parse_date("clip 16Feb2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16Feb25"), "2025-02-16")

    def test_compact_month_year(self):
        self.assertEqual(parse_date("TorrentDL_Mar2026"), "2026-03")

    def test_compact_forms_left_out(self):
        self.assertIsNone(parse_date("clip Feb162025"))
        self.assertIsNone(parse_date("clip 2025Feb16"))
        self.assertIsNone(parse_date("clip 2025Feb"))
        self.assertIsNone(parse_date("clip Mar26"))


class NumericAdditionTests(unittest.TestCase):
    def test_scene_release(self):
        self.assertEqual(parse_date("ExampleSite.25.02.16.Example.Title.1080p"), "2025-02-16")

    def test_scene_release_needs_dot_parts_on_both_sides(self):
        self.assertIsNone(parse_date("holiday 16.02.25"))
        self.assertIsNone(parse_date("25.02.16.Example.Title"))
        self.assertIsNone(parse_date("ExampleSite.25.02.16"))
        self.assertIsNone(parse_date("ExampleSite 25.02.16 Title"))

    def test_scene_release_is_year_month_day_only(self):
        self.assertIsNone(parse_date("ExampleSite.16.25.02.Title"))

    def test_year_month(self):
        self.assertEqual(parse_date("clip 2025-02"), "2025-02")
        self.assertEqual(parse_date("clip 2025.02"), "2025-02")
        self.assertEqual(parse_date("clip 2025_02"), "2025-02")

    def test_year_month_left_out_forms(self):
        self.assertIsNone(parse_date("clip 02-2025"))
        self.assertIsNone(parse_date("clip 02.2025"))
        self.assertIsNone(parse_date("clip 02_2025"))
        self.assertIsNone(parse_date("clip 202502"))
        self.assertIsNone(parse_date("clip 2025-13"))
        self.assertIsNone(parse_date("clip 2025-021"))

    def test_invalid_full_date_is_not_read_as_year_month(self):
        self.assertIsNone(parse_date("clip 2024-02-30"))

    def test_bracketed_year(self):
        self.assertEqual(parse_date("Example Movie (2019)"), "2019")
        self.assertEqual(parse_date("Example Movie [2019]"), "2019")

    def test_year_needs_its_own_brackets(self):
        self.assertIsNone(parse_date("Example Movie 2019"))
        self.assertIsNone(parse_date("Example Movie (2019 remaster)"))
        self.assertIsNone(parse_date("Example Movie (2019]"))
        self.assertIsNone(parse_date("Example Movie (1850)"))


class SelectionTests(unittest.TestCase):
    def test_full_date_beats_partial_date_to_its_left(self):
        self.assertEqual(parse_date("Example Movie (2019) 2025-07-30"), "2025-07-30")
        self.assertEqual(parse_date("clip Feb 2024 then 2025-07-30"), "2025-07-30")

    def test_month_beats_year(self):
        self.assertEqual(parse_date("Example Movie (2019) Feb 2025"), "2025-02")

    def test_leftmost_wins_among_equals(self):
        self.assertEqual(parse_date("clip 17-05-2024 then 2025-07-30"), "2024-05-17")
        self.assertEqual(parse_date("clip 2025-07-30 then Feb 16 2024"), "2025-07-30")
        self.assertEqual(parse_date("clip Feb 16 2024 then 2025-07-30"), "2024-02-16")

    def test_ambiguous_candidate_is_skipped(self):
        self.assertEqual(parse_date("05-06-2024 clip 2024-07-30"), "2024-07-30")

    def test_invalid_candidate_is_skipped(self):
        self.assertEqual(parse_date("2024-02-30 clip 2024-07-30"), "2024-07-30")


# 2025-02-16 00:00 UTC, still 2025-02-15 in Toronto
STAMP = "1739664000"


def parse_in_zone(filename, tz="UTC"):
    with mock.patch.dict(os.environ, {"TZ": tz}):
        return parse_date(filename)


class TimestampTests(unittest.TestCase):
    def test_whole_filename(self):
        self.assertEqual(parse_in_zone(STAMP), "2025-02-16")

    def test_prefix_or_suffix(self):
        self.assertEqual(parse_in_zone(f"{STAMP}_clip"), "2025-02-16")
        self.assertEqual(parse_in_zone(f"clip-{STAMP}"), "2025-02-16")
        self.assertEqual(parse_in_zone(f"clip {STAMP}"), "2025-02-16")
        self.assertEqual(parse_in_zone(f"{STAMP}.clip"), "2025-02-16")

    def test_milliseconds(self):
        self.assertEqual(parse_in_zone(f"clip_{STAMP}123"), "2025-02-16")

    def test_converted_in_container_zone(self):
        self.assertEqual(parse_in_zone(STAMP, "America/Toronto"), "2025-02-15")

    def test_not_in_the_middle(self):
        self.assertIsNone(parse_in_zone(f"clip_{STAMP}_clip"))

    def test_brackets_are_not_separators(self):
        self.assertIsNone(parse_in_zone(f"clip [original_{STAMP}]"))
        self.assertIsNone(parse_in_zone(f"[{STAMP}]"))

    def test_other_lengths_are_not_timestamps(self):
        self.assertIsNone(parse_in_zone("clip_173966400"))
        self.assertIsNone(parse_in_zone("clip_17396640001"))

    def test_range(self):
        # 1999-12-31 23:59:59 UTC
        self.assertIsNone(parse_in_zone("clip_0946684799"))
        # 2000-01-01 00:00 UTC
        self.assertEqual(parse_in_zone("clip_0946684800"), "2000-01-01")
        # 2100-01-01, in the future
        self.assertIsNone(parse_in_zone("clip_4102444800"))

    def test_lowest_priority(self):
        self.assertEqual(parse_in_zone(f"{STAMP}_Example Movie (2019)"), "2019")
        self.assertEqual(parse_in_zone(f"2001-02-03_{STAMP}"), "2001-02-03")


class FrenchAndSpanishTests(unittest.TestCase):
    def test_french(self):
        self.assertEqual(parse_date("clip 16 février 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16 févr. 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 3 août 2025"), "2025-08-03")
        self.assertEqual(parse_date("clip 1er mars 2025"), "2025-03-01")

    def test_french_without_accents(self):
        self.assertEqual(parse_date("clip 16 fevrier 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 3 aout 2025"), "2025-08-03")
        self.assertEqual(parse_date("clip 24 decembre 2025"), "2025-12-24")

    def test_french_decomposed_accents(self):
        decomposed = "clip 16 fe\u0301vrier 2025"
        self.assertEqual(parse_date(decomposed), "2025-02-16")

    def test_french_ordinal_only_on_the_first(self):
        self.assertEqual(parse_date("clip 2er mars 2025"), "2025-03")

    def test_spanish(self):
        self.assertEqual(parse_date("clip 16 de febrero de 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 16 febrero 2025"), "2025-02-16")
        self.assertEqual(parse_date("clip 1º de mayo de 2025"), "2025-05-01")
        self.assertEqual(parse_date("clip 24 dic 2025"), "2025-12-24")
        self.assertEqual(parse_date("clip 16 setiembre 2025"), "2025-09-16")

    def test_spanish_ordinal_only_on_the_first(self):
        self.assertEqual(parse_date("clip 2º de mayo de 2025"), "2025-05")

    def test_connectors_stay_in_their_language(self):
        # The month and year alone may still give a month-precision date
        self.assertNotEqual(parse_date("clip 16th de febrero de 2025"), "2025-02-16")
        self.assertNotEqual(parse_date("clip 16 of febrero 2025"), "2025-02-16")
        self.assertNotEqual(parse_date("clip 1er de febrero de 2025"), "2025-02-01")

    def test_spanish_set_is_not_a_month(self):
        # "set" is too common an English word to stand for septiembre
        self.assertIsNone(parse_date("clip 16 set 2025"))


def run_scraper(fragment, tz="UTC"):
    """Run the scraper as Stash would: JSON on stdin, JSON on stdout."""
    env = {**os.environ, "TZ": tz}
    result = subprocess.run(
        [sys.executable, "-B", SCRIPT],
        input=json.dumps(fragment),
        capture_output=True,
        text=True,
        env=env,
    )
    return json.loads(result.stdout)


def scene(path):
    return {"id": "1", "files": [{"path": path}]}


class ScriptTests(unittest.TestCase):
    def test_directory_names_are_ignored(self):
        fragment = scene("/data/example/TorrentDL_Mar2026/my movie 2025-07-30.mp4")
        self.assertEqual(run_scraper(fragment), {"date": "2025-07-30"})

    def test_directory_date_alone_gives_nothing(self):
        self.assertEqual(run_scraper(scene("/data/example/TorrentDL_Mar2026/my movie.mp4")), {})

    def test_extension_is_stripped(self):
        self.assertEqual(run_scraper(scene("/data/example/1739664000.mp4")), {"date": "2025-02-16"})

    def test_each_precision(self):
        self.assertEqual(run_scraper(scene("/data/example/clip Feb 16 2025.mp4")), {"date": "2025-02-16"})
        self.assertEqual(run_scraper(scene("/data/example/clip Feb 2025.mp4")), {"date": "2025-02"})
        self.assertEqual(run_scraper(scene("/data/example/Example Movie (2019).mp4")), {"date": "2019"})

    def test_no_files(self):
        self.assertIsNone(run_scraper({"id": "1", "files": []}))

    def test_time_zone_is_honored(self):
        fragment = scene("/data/example/1739664000.mp4")
        self.assertEqual(run_scraper(fragment, "America/Toronto"), {"date": "2025-02-15"})


if __name__ == "__main__":
    unittest.main()
