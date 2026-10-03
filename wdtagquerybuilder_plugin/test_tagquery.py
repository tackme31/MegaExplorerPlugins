"""python -m unittest test_tagquery"""

import unittest

from tagquery import MAX_SUGGESTIONS, TagIndex, query_text, words_of


def index_of(*files):
    index = TagIndex()
    for tags in files:
        index.add(tags)
    return index


class WordsOfTest(unittest.TestCase):
    def test_splits_general_tags_and_drops_the_prefix(self):
        self.assertEqual(words_of("wd:1girl  solo"), [("1girl", "general"), ("solo", "general")])

    def test_keeps_the_prefix_on_each_character(self):
        self.assertEqual(words_of("chara:hatsune_miku chara:kagamine_rin"),
                         [("chara:hatsune_miku", "chara"), ("chara:kagamine_rin", "chara")])

    def test_skips_ratings_and_empty_names(self):
        self.assertEqual(words_of("rating:general"), [])
        self.assertEqual(words_of("wd:"), [])
        self.assertEqual(words_of("chara: chara:"), [])

    def test_leaves_other_tags_whole(self):
        self.assertEqual(words_of("my tag"), [("my tag", "tag")])


class TagIndexTest(unittest.TestCase):
    def test_counts_files_per_word_ignoring_case(self):
        index = index_of(["wd:Solo smile"], ["wd:solo"], ["wd:smile"])
        self.assertEqual(index.count("solo"), 2)
        self.assertEqual(index.count("smile"), 2)
        self.assertEqual(index.files, 3)

    def test_names_a_word_by_its_most_common_spelling(self):
        index = index_of(["wd:Solo"], ["wd:solo"], ["wd:solo"])
        self.assertEqual(index.name("solo"), "solo")

    def test_drops_words_holding_a_quote(self):
        index = index_of(['wd:a"b ok'])
        self.assertEqual(set(index.files_by_word), {"ok"})

    def test_labels_show_the_kind(self):
        index = index_of(["wd:solo", "chara:miku", "mine"])
        self.assertEqual(index.label("solo"), "solo")
        self.assertEqual(index.label("chara:miku"), "miku   [chara]")
        self.assertEqual(index.label("mine"), "mine   [tag]")

    def test_counts_a_file_without_tags(self):
        index = index_of(None, [])
        self.assertEqual(index.files, 2)
        self.assertEqual(index.matches(["x"]), 0)


class SuggestTest(unittest.TestCase):
    def test_orders_exact_then_prefix_then_by_count(self):
        index = index_of(["wd:hair long_hair"], ["wd:long_hair"], ["wd:hairband"], ["wd:hairband"],
                         ["wd:hairband"])
        self.assertEqual(index.suggest("hair", set()), ["hair", "hairband", "long_hair"])

    def test_matches_a_character_by_its_bare_name(self):
        index = index_of(["chara:miku"], ["wd:mikuo"], ["wd:mikuo"])
        self.assertEqual(index.suggest("miku", set())[0], "chara:miku")

    def test_leaves_out_chosen_words_and_caps_the_list(self):
        index = index_of(["wd:" + " ".join(f"t{n}" for n in range(MAX_SUGGESTIONS + 10))])
        self.assertNotIn("t1", index.suggest("t", {"t1"}))
        self.assertEqual(len(index.suggest("t", set())), MAX_SUGGESTIONS)


class MatchesTest(unittest.TestCase):
    def test_needs_every_term_as_a_substring_of_some_tag(self):
        index = index_of(["wd:1girl solo_focus", "rating:general"], ["wd:solo"], ["wd:1girl"])
        self.assertEqual(index.matches(["solo"]), 2)
        self.assertEqual(index.matches(["girl", "SOLO"]), 1)
        self.assertEqual(index.matches(["general"]), 1)

    def test_counts_ratings_by_the_same_rule(self):
        index = index_of(["rating:general"], ["rating:generalx"], ["rating:explicit"])
        self.assertEqual(index.matches(["rating:general"]), 2)

    def test_matches_everything_without_terms(self):
        self.assertEqual(index_of(["a"], []).matches([]), 2)


class QueryTextTest(unittest.TestCase):
    def test_quotes_terms_holding_any_space_the_app_splits_at(self):
        self.assertEqual(query_text(["solo", "my tag", "a\tb", "c　d", "rating:general"]),
                         'tag:solo tag:"my tag" tag:"a\tb" tag:"c　d" tag:rating:general')

    def test_is_empty_without_terms(self):
        self.assertEqual(query_text([]), "")


if __name__ == "__main__":
    unittest.main()
