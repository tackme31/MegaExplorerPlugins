"""python -m unittest test_tags"""

import json
import tempfile
import unittest
from pathlib import Path

import numpy as np

from tags import Config, build_tags, has_been_tagged, is_taggable, load_config

NAMES = ["general", "sensitive", "1girl", "long_hair", "smile", "hatsune_miku", "kagamine_rin",
         "megurine_luka", "kaito"]
CATS = np.array([9, 9, 0, 0, 0, 4, 4, 4, 4])


def probs(*values):
    return np.array(values, dtype=np.float32)


class BuildTagsTest(unittest.TestCase):
    def test_orders_by_score_and_applies_thresholds(self):
        p = probs(0.9, 0.2, 0.99, 0.5, 0.29, 0.8, 0.6, 0.0, 0.0)
        self.assertEqual(
            build_tags(p, NAMES, CATS, Config()),
            ["wd:1girl long_hair", "rating:general", "character:hatsune_miku",
             "character:kagamine_rin"],
        )

    def test_keeps_only_the_best_rating_and_three_characters(self):
        p = probs(0.5, 0.7, 0.9, 0.0, 0.0, 0.9, 0.8, 0.7, 0.6)
        tags = build_tags(p, NAMES, CATS, Config())
        self.assertIn("rating:sensitive", tags)
        self.assertNotIn("rating:general", tags)
        self.assertNotIn("character:kaito", tags)
        self.assertEqual(len(tags), 5)

    def test_still_marks_an_item_with_no_general_tag(self):
        p = probs(0.0, 0.0, 0.1, 0.1, 0.1, 0.0, 0.0, 0.0, 0.0)
        self.assertEqual(build_tags(p, NAMES, CATS, Config()), ["wd:"])

    def test_drops_lowest_general_tags_past_the_byte_budget(self):
        p = probs(0.0, 0.0, 0.99, 0.9, 0.8, 0.0, 0.0, 0.0, 0.0)
        config = Config(max_general_bytes=len("wd:1girl long_hair"))
        self.assertEqual(build_tags(p, NAMES, CATS, config), ["wd:1girl long_hair"])

    def test_gives_up_extras_before_general_when_tag_slots_run_out(self):
        p = probs(0.9, 0.0, 0.99, 0.0, 0.0, 0.9, 0.0, 0.0, 0.0)
        user = [f"mine{i}" for i in range(8)]
        self.assertEqual(build_tags(p, NAMES, CATS, Config(), user),
                         ["wd:1girl", "rating:general"])
        self.assertEqual(build_tags(p, NAMES, CATS, Config(), user + ["mine8"]), ["wd:1girl"])
        self.assertEqual(build_tags(p, NAMES, CATS, Config(), user + ["mine8", "mine9"]), [])

    def test_ignores_its_own_old_tags_when_counting(self):
        p = probs(0.9, 0.0, 0.99, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        old = ["wd:x", "rating:explicit"] + [f"mine{i}" for i in range(8)]
        self.assertEqual(build_tags(p, NAMES, CATS, Config(), old), ["wd:1girl", "rating:general"])

    def test_trims_general_to_fit_the_total_byte_limit(self):
        p = probs(0.0, 0.0, 0.99, 0.9, 0.0, 0.0, 0.0, 0.0, 0.0)
        user = ["x" * (3000 - len(",wd:1girl"))]
        self.assertEqual(build_tags(p, NAMES, CATS, Config(), user), ["wd:1girl"])


class HelpersTest(unittest.TestCase):
    def test_taggable_by_extension(self):
        self.assertTrue(is_taggable("a.PNG"))
        self.assertTrue(is_taggable("clip.mp4"))
        self.assertFalse(is_taggable("doc.pdf"))
        self.assertFalse(is_taggable("README"))

    def test_has_been_tagged(self):
        self.assertTrue(has_been_tagged(["mine", "wd:1girl"]))
        self.assertFalse(has_been_tagged(["rating:general"]))
        self.assertFalse(has_been_tagged(None))

    def test_config_overrides_known_keys_only(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.json"
            path.write_text(json.dumps({"thresh_general": 0.5, "unknown": 1}), encoding="utf-8")
            config = load_config(path)
            self.assertEqual(config.thresh_general, 0.5)
            self.assertEqual(config.thresh_character, 0.50)
            self.assertEqual(load_config(Path(d) / "missing.json"), Config())


if __name__ == "__main__":
    unittest.main()
