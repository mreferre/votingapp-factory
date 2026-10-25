import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Avoid any real AWS access: boto3.resource is mocked before app.py is imported.
with mock.patch("boto3.resource"):
    import app as votingapp


class FakeTable:
    def __init__(self):
        self.counts = {"outback": 1, "bucadibeppo": 2, "ihop": 3, "chipotle": 4}

    def get_item(self, Key):
        return {"Item": {"name": Key["name"], "restaurantcount": self.counts[Key["name"]]}}

    def update_item(self, Key, ExpressionAttributeValues, **kwargs):
        self.counts[Key["name"]] = ExpressionAttributeValues[":value"]


class VotingAppTest(unittest.TestCase):
    def setUp(self):
        self.table = FakeTable()
        patcher = mock.patch.object(votingapp, "ddbtable", self.table)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = votingapp.app.test_client()

    def test_home_does_not_advertise_heavy_votes(self):
        body = self.client.get("/").get_data(as_text=True)
        self.assertIn("/api/getvotes", body)
        self.assertNotIn("getheavyvotes", body)

    def test_getheavyvotes_is_removed(self):
        self.assertEqual(self.client.get("/api/getheavyvotes").status_code, 404)

    def test_vote_routes_increment(self):
        for name, start in (("outback", 1), ("bucadibeppo", 2), ("ihop", 3), ("chipotle", 4)):
            resp = self.client.get("/api/" + name)
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.get_data(as_text=True), str(start + 1))

    def test_getvotes(self):
        resp = self.client.get("/api/getvotes")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(
            resp.get_json(force=True),
            [
                {"name": "outback", "value": 1},
                {"name": "bucadibeppo", "value": 2},
                {"name": "ihop", "value": 3},
                {"name": "chipotle", "value": 4},
            ],
        )

    def test_no_stress_leftovers(self):
        for attr in ("memeater", "f", "cpustressfactor", "memstressfactor", "Pool", "cpu_count", "randrange"):
            self.assertFalse(hasattr(votingapp, attr), attr)


if __name__ == "__main__":
    unittest.main()
