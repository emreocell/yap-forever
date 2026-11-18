"""A damaged cache file or a broken download gives a next step, never a traceback."""
import gzip
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from yap_forever import bnet, cli, gamedata, prices, settings
from tests.test_bnet import CREDS, FakeOpener, FakeResp
from tests.test_cli import run
from tests.test_prices_refresh import FakeHouses, fetch


class DamagedCacheTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.paths = settings.paths(Path(self._tmp.name) / "home")
        run(["init"], self.paths)
        stock = self.paths.character("Firstname Lastname") / "stock.toml"
        stock.parent.mkdir(parents=True)
        stock.write_text("level = 20\n[items]\n", encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def test_check_damaged_prices(self):
        self.paths.prices.write_text("{", encoding="utf-8")
        code, out = run(["check", "--offline"], self.paths)
        self.assertEqual(code, 1)
        line = next(l for l in out.splitlines() if l.startswith("prices"))
        self.assertIn("damaged", line)
        self.assertIn(cli.command_hint("prices"), line)

    def test_check_damaged_house(self):
        self.paths.house.write_text("{}", encoding="utf-8")
        code, out = run(["check", "--offline"], self.paths)
        self.assertEqual(code, 1)
        line = next(l for l in out.splitlines() if l.startswith("house"))
        self.assertIn("damaged", line)
        self.assertIn("probe", line)

    def test_plan_damaged_prices(self):
        self.paths.prices.write_text('{"listings": ', encoding="utf-8")
        code, out = run(["plan", "--character", "Firstname Lastname"], self.paths)
        self.assertEqual(code, 1)
        self.assertIn("damaged", out)
        self.assertIn(cli.command_hint("prices"), out)

    def test_plan_damaged_house(self):
        self.paths.prices.write_text('{"snapshot_time": "t", "listings": {}}', encoding="utf-8")
        self.paths.house.write_text('{"house": "x"}', encoding="utf-8")
        code, out = run(["plan", "--character", "Firstname Lastname"], self.paths)
        self.assertEqual(code, 1)
        self.assertIn("damaged", out)

    def test_prices_refresh_replaces_damaged_file(self):
        path = Path(self._tmp.name) / "prices.json"
        path.write_text("{", encoding="utf-8")
        self.assertEqual(fetch(FakeHouses("12:00", "12:00"), 10, path), 0)
        self.assertEqual(prices.Market.load(path).house, 10)


class BrokenDownloadTests(unittest.TestCase):
    def test_truncated_gzip_is_api_error(self):
        raw = gzip.compress(b'{"auctions": []}')[:-6]
        api = lambda req: FakeResp(raw, {"Content-Encoding": "gzip"})
        with tempfile.TemporaryDirectory() as d:
            c = bnet.Client(CREDS, opener=FakeOpener(api=api), now=lambda: 1000.0,
                            token_cache=Path(d) / "token.json")
            with self.assertRaises(bnet.ApiError) as cm:
                c.get("/x")
        self.assertIn("damaged response", str(cm.exception))

    def test_bad_json_is_api_error(self):
        api = lambda req: FakeResp(b'{"auctions": [')
        with tempfile.TemporaryDirectory() as d:
            c = bnet.Client(CREDS, opener=FakeOpener(api=api), now=lambda: 1000.0,
                            token_cache=Path(d) / "token.json")
            with self.assertRaises(bnet.ApiError):
                c.get("/x")

    def test_killed_game_data_download_leaves_no_file(self):
        real_write = Path.write_bytes

        def half_write(path, data):  # the process dies halfway through writing the file
            real_write(path, data[: len(data) // 2])
            raise OSError("killed")

        with tempfile.TemporaryDirectory() as d, \
                mock.patch("urllib.request.urlopen", return_value=FakeResp(b"x" * 100)), \
                mock.patch.object(Path, "write_bytes", half_write):
            with self.assertRaises(OSError):
                gamedata.fetch_all(dest=Path(d))
            self.assertEqual(list(Path(d).iterdir()), [])


if __name__ == "__main__":
    unittest.main()
