import json
import tempfile
import unittest
from pathlib import Path

from yap_forever import profile, settings
from yap_forever.migrate import migrate


class MigrateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        t = Path(self._tmp.name)
        self.user, self.data = t / "user", t / "data"
        (self.data / "gamedata").mkdir(parents=True)
        self.user.mkdir()
        (self.user / "stock.toml").write_text("level = 47\n[items]\n", encoding="utf-8")
        (self.user / "alt2-bags.toml").write_text("profs = [197]\nbag_slots = 30\n", encoding="utf-8")
        (self.data / "house.json").write_text('{"house": 4242, "found": "x"}', encoding="utf-8")
        (self.data / "prices.json").write_text('{"snapshot_time": "t", "listings": {}}', encoding="utf-8")
        (self.data / "gamedata" / "Recipes.lua").write_text("-- data", encoding="utf-8")
        (self.data / "config.json").write_text('{"client_id": "SECRET-ID"}', encoding="utf-8")
        self.dest = settings.paths(t / "home")

    def tearDown(self):
        self._tmp.cleanup()

    def run_migrate(self):
        return migrate(self.user, self.data, self.dest, "Ana", {"Bo": self.user / "alt2-bags.toml"})

    def test_migrate_copies_files_into_home_layout(self):
        self.run_migrate()
        self.assertIn("level = 47", (self.dest.character("Ana") / "stock.toml").read_text(encoding="utf-8"))
        self.assertIn("bag_slots = 30", (self.dest.character("Bo") / "bags.toml").read_text(encoding="utf-8"))
        self.assertEqual(profile.load_house(self.dest.house), 4242)
        self.assertTrue(self.dest.prices.exists())
        self.assertTrue((self.dest.gamedata / "Recipes.lua").exists())
        prof = profile.load_profile(self.dest.profile)
        self.assertEqual(set(prof.characters), {"Ana", "Bo"})
        self.assertEqual(prof.faction, "alliance")

    def test_migrate_adds_goals(self):
        from yap_forever.config import Goal, load_stock
        (self.user / "stock.toml").write_text("level = 47\ntarget = 200\n[items]\n", encoding="utf-8")
        self.run_migrate()
        s = load_stock(self.dest.character("Ana") / "stock.toml")
        self.assertEqual(s.goals, {164: Goal(skill=200), 333: Goal(skill=200)})

    def test_migrate_keeps_existing_goals(self):
        text = "level = 47\n[items]\n\n[goals]\ntailoring = 150\n"
        (self.user / "stock.toml").write_text(text, encoding="utf-8")
        self.run_migrate()
        self.assertEqual((self.dest.character("Ana") / "stock.toml").read_text(encoding="utf-8"), text)

    def test_migrate_copies_and_keeps_existing_profile(self):
        self.dest.root.mkdir(parents=True)
        self.dest.profile.write_text('region = "us"\nfaction = "horde"\n', encoding="utf-8")
        self.run_migrate()
        self.assertEqual(self.dest.profile.read_text(encoding="utf-8"), 'region = "us"\nfaction = "horde"\n')

    def test_migrate_never_copies_config_json(self):
        self.run_migrate()
        for p in self.dest.root.rglob("*"):
            if p.is_file():
                self.assertNotIn("SECRET-ID", p.read_text(encoding="utf-8", errors="replace"), p)
        self.assertFalse(self.dest.credentials.exists())



class NamesWithSpacesTests(MigrateTests):
    def test_names_with_spaces_and_accents_load(self):
        migrate(self.user, self.data, self.dest, "Ana Brightforge",
                {"Élise Brightforge": self.user / "alt2-bags.toml"})
        prof = profile.load_profile(self.dest.profile)
        self.assertEqual(set(prof.characters), {"Ana Brightforge", "Élise Brightforge"})
        self.assertTrue((self.dest.character("Ana Brightforge") / "stock.toml").exists())


class MigrateCliTests(MigrateTests):
    def test_cli_migrate_parses_alts(self):
        import contextlib, io
        from yap_forever import cli
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["migrate", "--from-user", str(self.user), "--from-data", str(self.data),
                             "--main", "Ana", "--alt", f"Bo={self.user / 'alt2-bags.toml'}"], self.dest)
        self.assertEqual(code, 0)
        self.assertTrue((self.dest.character("Bo") / "bags.toml").exists())

    def test_cli_migrate_region_ruleset_faction(self):
        import contextlib, io
        from yap_forever import cli
        with contextlib.redirect_stdout(io.StringIO()):
            code = cli.main(["migrate", "--from-user", str(self.user), "--from-data", str(self.data),
                             "--main", "Ana", "--region", "us", "--ruleset", "3", "--faction", "horde"],
                            self.dest)
        self.assertEqual(code, 0)
        prof = profile.load_profile(self.dest.profile)
        self.assertEqual((prof.region, prof.ruleset, prof.faction), ("us", 3, "horde"))
        saved = json.loads(self.dest.house.read_text(encoding="utf-8"))
        self.assertEqual((saved["house"], saved["region"], saved["ruleset"]), (4242, "us", 3))

    def test_cli_migrate_defaults_to_eu_alliance(self):
        import contextlib, io
        from yap_forever import cli
        with contextlib.redirect_stdout(io.StringIO()):
            cli.main(["migrate", "--from-user", str(self.user), "--from-data", str(self.data),
                      "--main", "Ana"], self.dest)
        prof = profile.load_profile(self.dest.profile)
        self.assertEqual((prof.region, prof.ruleset, prof.faction), ("eu", 2, "alliance"))


if __name__ == "__main__":
    unittest.main()
