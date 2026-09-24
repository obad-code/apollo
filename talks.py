"""Your recent talks with Apollo, for the display's Talks tab.

Read from the record (journal.py): each thing you said, paired with the
answer that followed it and the tools used on the way, newest first, over
today and yesterday.
"""

import datetime

import journal


def recent(limit=15, today=None):
    today = today or datetime.date.today()
    yesterday = today - datetime.timedelta(days=1)
    exchanges = []
    current = None
    for day in (yesterday, today):
        for entry in journal.day(day):
            kind = entry.get("kind")
            if kind == "you":
                current = {"at": entry.get("at", ""), "you": entry.get("text", ""),
                           "apollo": "", "who": "Apollo", "tools": [],
                           "day": "today" if day == today else "yesterday"}
                exchanges.append(current)
            elif current is None or current["apollo"]:
                continue
            elif kind == "tool":
                current["tools"].append(entry.get("name", ""))
            elif kind == "apollo":
                current["apollo"] = entry.get("text", "")
                current["who"] = entry.get("who") or "Apollo"
    for exchange in exchanges:
        exchange["time"] = exchange["at"][11:16]
    return list(reversed(exchanges))[:limit]
