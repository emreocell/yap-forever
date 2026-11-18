"""Refreshing prices must never keep another house's prices or stale commodity prices."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from yap_forever import prices
from yap_forever.bnet import Response


class FakeHouses:
    """Answers per house; 304 when If-Modified-Since is not older than the snapshot."""

    def __init__(self, regular_time: str, comm_time: str, regular_price=100, comm_price=7):
        self.t = {"regular": regular_time, "comm": comm_time}
        self.price = {"regular": regular_price, "comm": comm_price}
        self.calls = []

    def get(self, path, if_modified_since=None):
        kind = "comm" if path.endswith("/commodities") else "regular"
        house = int(path.split("/auctions/")[1].split("/")[0])
        self.calls.append((kind, house, if_modified_since))
        if if_modified_since is not None and if_modified_since >= self.t[kind]:
            return Response(304, None, if_modified_since)
        if kind == "regular":
            body = {"auctions": [{"item": {"id": 2851}, "buyout": self.price["regular"] + house, "quantity": 1}]}
        else:
            body = {"auctions": [{"item": {"id": 2840}, "unit_price": self.price["comm"], "quantity": 50}]}
        return Response(200, body, self.t[kind])


def fetch(client, house, path):
    with contextlib.redirect_stdout(io.StringIO()):
        return prices.fetch(client, house, 2, path, path.with_name("log.txt"), region="eu")


class RefreshTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "prices.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_new_house_ignores_old_snapshot_time(self):
        fetch(FakeHouses("12:00", "12:00"), 10, self.path)
        code = fetch(FakeHouses("11:00", "11:00"), 11, self.path)  # older snapshot, other house
        self.assertEqual(code, 0)
        m = prices.Market.load(self.path)
        self.assertEqual(m.house, 11)
        self.assertEqual(m.min_price(2851), 100 + 11)

    def test_commodities_refreshed_when_auctions_unchanged(self):
        fetch(FakeHouses("12:00", "12:00", comm_price=7), 11, self.path)
        fetch(FakeHouses("12:00", "13:00", comm_price=9), 11, self.path)
        self.assertEqual(prices.Market.load(self.path).min_price(2840), 9)

    def test_both_unchanged_keeps_file_and_skips_download(self):
        fetch(FakeHouses("12:00", "12:00"), 11, self.path)
        before = self.path.read_bytes()
        client = FakeHouses("12:00", "12:00")
        fetch(client, 11, self.path)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertTrue(all(since is not None for _, _, since in client.calls))


if __name__ == "__main__":
    unittest.main()
