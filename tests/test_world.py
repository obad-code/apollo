"""OSIRIS mode's own panel: what is happening in the world - the day's
strongest earthquakes (USGS) and the world's headlines - in place of the
stocks and the machine's meters, which have nothing to do with a map."""
import json

import world

USGS = json.dumps({"features": [
    {"properties": {"mag": 4.6, "place": "12 km S of Hualien City, Taiwan", "time": 1790400000000,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/a"}},
    {"properties": {"mag": 6.2, "place": "Kermadec Islands region", "time": 1790390000000,
                    "url": "https://earthquake.usgs.gov/earthquakes/eventpage/b"}},
    {"properties": {"mag": None, "place": "nowhere", "time": 1790380000000, "url": ""}},
    {"properties": {"mag": 5.1, "place": "<b>Peru</b>", "time": 1790395000000,
                    "url": "javascript:alert(1)"}},
]})


def test_the_strongest_come_first():
    quakes = world.parse_quakes(USGS)
    assert [q["mag"] for q in quakes] == [6.2, 5.1, 4.6]
    assert quakes[0]["place"] == "Kermadec Islands region"
    assert quakes[0]["when"] == 1790390000.0


def test_only_usgs_links_are_kept():
    quakes = world.parse_quakes(USGS)
    peru = next(q for q in quakes if q["mag"] == 5.1)
    assert peru["link"] == ""
    assert quakes[0]["link"].startswith("https://earthquake.usgs.gov/")


def test_damaged_answers_are_nothing():
    assert world.parse_quakes("not json") == []
    assert world.parse_quakes(json.dumps({"features": "no"})) == []


def test_how_many(monkeypatch):
    assert len(world.parse_quakes(USGS, limit=2)) == 2
