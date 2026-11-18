import unittest

from yap_forever.lualit import extract_table, parse


class ParseTests(unittest.TestCase):
    def test_lualit_positional_nil(self):
        self.assertEqual(parse('{"a",nil,{{3}}}'), ["a", None, [[3]]])

    def test_lualit_keyed(self):
        self.assertEqual(parse('{[818] = { 1, 25 }, x = false}'), {818: [1, 25], "x": False})

    def test_comments_and_trailing_commas(self):
        text = '{\n\t[818] = { 1, 25, 50, 75 }, -- Basic Campfire\n\t[2149] = { 1.5, -2 },\n}'
        self.assertEqual(parse(text), {818: [1, 25, 50, 75], 2149: [1.5, -2]})

    def test_string_escapes_and_braces(self):
        self.assertEqual(parse(r'{"a \"q\" {x}", ["k"] = true}'), {1: 'a "q" {x}', "k": True})

    def test_empty_table(self):
        self.assertEqual(parse("{}"), [])


class ExtractTests(unittest.TestCase):
    def test_extract_ns_table(self):
        src = 'local _, ns = ...\nns.Foo = {\n [1] = { 2 }, -- "}" in comment\n}\nns.Bar = { 3 }\n'
        self.assertEqual(parse(extract_table(src, "Foo")), {1: [2]})
        self.assertEqual(parse(extract_table(src, "Bar")), [3])

    def test_extract_questdata(self):
        src = 'QuestieDB.questData = [[return {\n[8] = {"A Rogue\'s Deal",nil},\n}]]\n'
        self.assertEqual(parse(extract_table(src, "questData")), {8: ["A Rogue's Deal", None]})

    def test_extract_missing_raises(self):
        with self.assertRaises(KeyError):
            extract_table("ns.Foo = {}", "Nope")


if __name__ == "__main__":
    unittest.main()
