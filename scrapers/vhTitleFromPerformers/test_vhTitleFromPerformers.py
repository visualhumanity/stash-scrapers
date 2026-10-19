import contextlib
import io
import json
import os
import subprocess
import sys
import types
import unittest
from unittest import mock

import vhTitleFromPerformers

SCRIPT = os.path.join(os.path.dirname(os.path.realpath(__file__)), "vhTitleFromPerformers.py")

# All sample names in this file are made up


def performer(name, gender=None, rating=None, performer_id="1"):
    return {"id": performer_id, "name": name, "gender": gender, "rating100": rating}


def scrape(performers, scene_id="1"):
    """Run scrape() against a fake Stash API whose scene has these performers."""
    result = {"findScene": {"performers": performers}}
    return scrape_with_api(mock.Mock(return_value=result), scene_id)


def scrape_with_api(call, scene_id="1"):
    fake = types.ModuleType("py_common.graphql")
    fake.callGraphQL = call
    with mock.patch.dict(sys.modules, {"py_common.graphql": fake}):
        return vhTitleFromPerformers.scrape({"id": scene_id})


def run_scraper(stdin_text, env=None):
    """Run the scraper as Stash would: JSON on stdin, JSON on stdout."""
    return subprocess.run(
        [sys.executable, "-B", SCRIPT],
        input=stdin_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
    )


def title(*performers):
    return scrape(list(performers))["title"]


class FormatTests(unittest.TestCase):
    def test_two_performers_join_with_ampersand(self):
        self.assertEqual(title(performer("Amy"), performer("Bea")), "Amy & Bea")

    def test_three_performers_use_oxford_comma(self):
        self.assertEqual(
            title(performer("Amy"), performer("Bea"), performer("Cal")),
            "Amy, Bea, & Cal",
        )

    def test_four_performers_use_oxford_comma(self):
        self.assertEqual(
            title(performer("Amy"), performer("Bea"), performer("Cal"), performer("Dee")),
            "Amy, Bea, Cal, & Dee",
        )

    def test_disambiguation_is_not_in_the_title(self):
        amy = dict(performer("Amy"), disambiguation="Example Studio")
        self.assertEqual(title(amy, performer("Bea")), "Amy & Bea")

    def test_only_the_title_is_returned(self):
        self.assertEqual(set(scrape([performer("Amy"), performer("Bea")])), {"title"})


class SkipTests(unittest.TestCase):
    def test_fewer_than_two_performers_suggest_no_title(self):
        for performers in ([], [performer("Amy")]):
            with self.subTest(count=len(performers)):
                stderr = io.StringIO()
                with contextlib.redirect_stderr(stderr):
                    self.assertEqual(scrape(performers), {})
                self.assertIn("\x01i\x02", stderr.getvalue())


class ApiTests(unittest.TestCase):
    def assert_fails_with_error_log(self, call):
        stderr = io.StringIO()
        with contextlib.redirect_stderr(stderr):
            self.assertIsNone(scrape_with_api(call))
        self.assertIn("\x01e\x02", stderr.getvalue())

    def test_queries_the_fragment_scene(self):
        call = mock.Mock(return_value={"findScene": {"performers": [performer("Amy"), performer("Bea")]}})
        scrape_with_api(call, scene_id="42")
        self.assertEqual(call.call_args.args[1], {"id": "42"})

    def test_api_returning_nothing_is_a_failure(self):
        # py_common returns None after logging a missing URL, a 401 or a 404
        self.assert_fails_with_error_log(mock.Mock(return_value=None))

    def test_api_raising_is_a_failure(self):
        for error in (ConnectionError("unexpected status"), OSError("network down"), ValueError("bad JSON")):
            with self.subTest(error=type(error).__name__):
                self.assert_fails_with_error_log(mock.Mock(side_effect=error))

    def test_scene_not_found_is_a_failure(self):
        self.assert_fails_with_error_log(mock.Mock(return_value={"findScene": None}))


class CharacterTests(unittest.TestCase):
    """Names are copied into the title exactly; sort order for these is not part of the spec."""

    NAMES = {
        "diacritics": "Exámple Peña Çedilla",
        "greek": "Παράδειγμα αΔΩ",
        "mixed case": "eXample McTEST",
        "digits": "Example 69",
        "special characters": "Ex! A/B $5 Ex & Ample _x_ Jean-Ex (Jr)",
        "emoji": "Example \U0001f351 \U0001f346\U0001f924",
        "single word": "Example",
        "multi word": "Example Performer Name",
    }

    def test_names_pass_through_unchanged(self):
        for kind, name in self.NAMES.items():
            with self.subTest(kind=kind):
                result = title(performer(name), performer(name))
                self.assertEqual(result, f"{name} & {name}")


class GenderOrderTests(unittest.TestCase):
    def test_female_and_trans_genders_sort_after_male(self):
        for gender in ("FEMALE", "TRANSGENDER_MALE", "TRANSGENDER_FEMALE", "INTERSEX", "NON_BINARY"):
            with self.subTest(gender=gender):
                self.assertEqual(title(performer("Amy", gender), performer("Zed", "MALE")), "Zed & Amy")

    def test_unset_gender_sorts_with_male(self):
        self.assertEqual(
            title(performer("Cal", "FEMALE"), performer("Bea"), performer("Amy", "MALE")),
            "Amy, Bea, & Cal",
        )


class RatingOrderTests(unittest.TestCase):
    def test_tiers_are_high_then_unrated_then_low(self):
        self.assertEqual(
            title(performer("Amy", rating=20), performer("Bea"), performer("Cal", rating=80)),
            "Cal, Bea, & Amy",
        )

    def test_cutoff_of_three_stars_is_in_the_high_tier(self):
        self.assertEqual(title(performer("Bea"), performer("Zed", rating=60)), "Zed & Bea")

    def test_just_below_cutoff_is_in_the_low_tier(self):
        self.assertEqual(title(performer("Amy", rating=59), performer("Zed")), "Zed & Amy")

    def test_higher_rating_first_within_a_tier(self):
        self.assertEqual(
            title(performer("Amy", rating=60), performer("Bea", rating=100), performer("Cal", rating=80)),
            "Bea, Cal, & Amy",
        )
        self.assertEqual(
            title(performer("Amy", rating=10), performer("Bea", rating=40), performer("Cal", rating=20)),
            "Bea, Cal, & Amy",
        )

    def test_gender_group_comes_before_rating(self):
        self.assertEqual(
            title(performer("Amy", "FEMALE", rating=100), performer("Zed", "MALE", rating=10)),
            "Zed & Amy",
        )

    def test_rating_tiers_apply_within_each_gender_group(self):
        self.assertEqual(
            title(
                performer("Amy", "FEMALE", rating=20),
                performer("Bea", "FEMALE"),
                performer("Cal", "FEMALE", rating=90),
                performer("Dan", "MALE", rating=30),
                performer("Eli", "MALE", rating=70),
            ),
            "Eli, Dan, Cal, Bea, & Amy",
        )


class NameOrderTests(unittest.TestCase):
    def test_same_rating_sorts_by_name_ignoring_case(self):
        self.assertEqual(
            title(performer("Bea", rating=80), performer("alex", rating=80), performer("Cal", rating=80)),
            "alex, Bea, & Cal",
        )

    def test_unrated_sort_by_name_ignoring_case(self):
        self.assertEqual(title(performer("bea"), performer("Amy")), "Amy & bea")

    def test_names_equal_ignoring_case_sort_by_exact_name(self):
        self.assertEqual(title(performer("alex", performer_id="1"), performer("Alex", performer_id="2")), "Alex & alex")

    def test_title_does_not_depend_on_api_order(self):
        performers = [
            performer("Alex", rating=80, performer_id="9"),
            performer("Alex", rating=80, performer_id="10"),
            performer("alex", rating=80, performer_id="3"),
            performer("Bea", rating=80, performer_id="1"),
        ]
        for order in (performers, performers[::-1], performers[2:] + performers[:2]):
            with self.subTest(order=[p["id"] for p in order]):
                self.assertEqual(title(*order), "Alex, Alex, alex, & Bea")


class HarnessTests(unittest.TestCase):
    """Inputs that fail before any Stash API call."""

    def assert_prints_null(self, stdin_text):
        proc = run_scraper(stdin_text)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertIsNone(json.loads(proc.stdout))
        self.assertIn("\x01e\x02", proc.stderr)

    def test_invalid_json_prints_null(self):
        self.assert_prints_null("not json")

    def test_fragment_without_id_prints_null(self):
        for fragment in (None, {}, {"id": ""}, {"id": None}, [], "1"):
            with self.subTest(fragment=fragment):
                self.assert_prints_null(json.dumps(fragment))


if __name__ == "__main__":
    unittest.main()
