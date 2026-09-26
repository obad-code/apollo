"""What is happening in the world, for OSIRIS mode's own panel: the day's
strongest earthquakes, from the USGS's public feed (no key), and the world's
headlines, from the news search feeds.py already reads. The map is OSIRIS's
own window and Apollo cannot read it; this is what goes beside it.

Nothing here raises: a source that fails is an empty list.
"""

import json
import logging
import urllib.request

import feeds

log = logging.getLogger("apollo.world")

QUAKES_URL = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_day.geojson"
# Google News's own World section: its editors' pick of the world's news,
# which a search for "world news" is not.
WORLD_URL = "https://news.google.com/rss/headlines/section/topic/WORLD?hl=en-US&gl=US&ceid=US:en"
QUAKES = 6
HEADLINES = 7


def parse_quakes(body, limit=QUAKES):
    """USGS GeoJSON -> [{mag, place, when, link}], the strongest first."""
    try:
        features = json.loads(body).get("features")
    except (ValueError, AttributeError, TypeError):
        return []
    if not isinstance(features, list):
        return []
    quakes = []
    for feature in features:
        props = (feature or {}).get("properties") or {} if isinstance(feature, dict) else {}
        mag = props.get("mag")
        if not isinstance(mag, (int, float)):
            continue
        link = str(props.get("url") or "")
        quakes.append({"mag": round(float(mag), 1), "place": str(props.get("place") or ""),
                       "when": float(props.get("time") or 0) / 1000,
                       # Only the USGS's own pages: the link is opened on a click.
                       "link": link if link.startswith("https://earthquake.usgs.gov/") else ""})
    quakes.sort(key=lambda q: (-q["mag"], -q["when"]))
    return quakes[:limit]


def quakes(limit=QUAKES):
    try:
        request = urllib.request.Request(QUAKES_URL, headers=feeds.HEADERS)
        with urllib.request.urlopen(request, timeout=10) as response:
            return parse_quakes(response.read().decode("utf-8", "replace"), limit)
    except Exception as e:  # noqa: BLE001 - no quakes is an empty list, not an error
        log.info("USGS did not answer: %s", e)
        return []


def headlines(limit=HEADLINES):
    try:
        return [dict(story, summary="", image="")
                for story in feeds._read(WORLD_URL, feeds.parse_news)][:limit]
    except Exception as e:  # noqa: BLE001
        log.info("world headlines failed: %s", e)
        return []
