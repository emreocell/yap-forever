import os
import tempfile
import unittest
from pathlib import Path

from yap_forever import config, settings

STOCK = """
level = 37
favor = 245
cash_gold = 12
mining = 171
short_farm_ore = 200

[items]
2840 = 195
2841 = 238

[marker]
item_id = 0
buyout_copper = 0
"""


def write(dirpath, name, text, mode=0o600):
    p = Path(dirpath) / name
    p.write_text(text)
    os.chmod(p, mode)
    return p


class StockTests(unittest.TestCase):
    def test_load_stock_values(self):
        with tempfile.TemporaryDirectory() as d:
            s = config.load_stock(write(d, "stock.toml", STOCK, 0o644))
        self.assertEqual(s.favor, 245)
        self.assertEqual(s.cash, 120000)
        self.assertEqual(s.items[2841], 238)
        self.assertEqual(s.level, 37)
        self.assertEqual(s.mining, 171)
        self.assertEqual(s.short_farm_ore, 200)
        self.assertIsNone(s.marker)
        self.assertEqual(s.target, 225)
        self.assertEqual(s.mining_goal, 171)

    def test_target_and_mining_goal(self):
        text = "target = 300\nmining_goal = 250\n" + STOCK
        with tempfile.TemporaryDirectory() as d:
            s = config.load_stock(write(d, "stock.toml", text, 0o644))
        self.assertEqual((s.target, s.mining_goal), (300, 250))
        self.assertIsNone(s.quest_item_sales)
        s2 = config.load_stock(write(d2 := tempfile.mkdtemp(), "stock.toml", "quest_item_sales = 20\n" + STOCK, 0o644))
        self.assertEqual(s2.quest_item_sales, 20)

    def test_marker_set(self):
        text = STOCK.replace("item_id = 0", "item_id = 2589").replace(
            "buyout_copper = 0", "buyout_copper = 71313")
        with tempfile.TemporaryDirectory() as d:
            s = config.load_stock(write(d, "stock.toml", text, 0o644))
        self.assertEqual(s.marker, (2589, 71313))


class SkillsTests(unittest.TestCase):
    def test_load_stock_skills_by_name(self):
        with tempfile.TemporaryDirectory() as d:
            s = config.load_stock(write(d, "stock.toml", STOCK + "\n[skills]\nblacksmithing = 184\nenchanting = 200\n"))
        self.assertEqual(s.skills, {164: 184, 333: 200})

    def test_unknown_profession_name_raises(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ValueError):
                config.load_stock(write(d, "stock.toml", STOCK + "\n[skills]\nbasketweaving = 10\n"))


class CredentialTests(unittest.TestCase):
    def test_credentials_repr_masks(self):
        c = config.Credentials("myclientid", "s3cr3tvalue", "eu")
        self.assertNotIn("s3cr3tvalue", repr(c))
        self.assertNotIn("myclientid", repr(c))
        self.assertNotIn("s3cr3tvalue", str(c))

    @unittest.skipIf(os.name == "nt", "file modes are POSIX only")
    def test_credentials_refuses_open_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(d, "config.json",
                      '{"client_id": "a", "client_secret": "b", "region": "eu"}', 0o644)
            with self.assertRaises(PermissionError):
                settings.load_credentials(p)

    def test_credentials_empty_values(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(d, "config.json",
                      '{"client_id": "", "client_secret": "", "region": "eu"}')
            with self.assertRaises(ValueError) as cm:
                settings.load_credentials(p)
        self.assertIn("fill in client_id and client_secret in config.json", str(cm.exception))

    def test_credentials_load(self):
        with tempfile.TemporaryDirectory() as d:
            p = write(d, "config.json",
                      '{"client_id": "a", "client_secret": "b", "region": "eu"}')
            c = settings.load_credentials(p)
        self.assertEqual((c.client_id, c.client_secret, c.region), ("a", "b", "eu"))


if __name__ == "__main__":
    unittest.main()
