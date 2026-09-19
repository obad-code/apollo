"""The day's recap, from live sources: what Apollo gathers and what it says.

Run:  .venv/Scripts/python.exe probes/probe_briefing.py [--speak]
With --speak it also has Gemini read it aloud (needs GEMINI_API_KEY).
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

import briefing  # noqa: E402
import dataservice  # noqa: E402

start = time.monotonic()
payload = briefing.compose()
gathered = time.monotonic() - start

print(f"gathered in {gathered:.1f}s")
print(f"date     {payload['date']}  ({payload['hijri']}, day {payload['day_of_year']}, week {payload['week']})")
print(f"weather  {payload['weather']}")
print(f"market   {payload['market']['status']}")
for quote in payload["market"]["indices"] + payload["market"]["movers"]:
    print(f"         {quote['symbol']:7} {quote['price']:>10,.2f} {quote['change_pct']:+.2f}%")
for topic, items in payload["headlines"].items():
    for item in items:
        print(f"{topic:8} {item['title'][:70]} ({item['source']}, {item['age']})")
for post in payload["posts"]:
    print(f"post     {'[market] ' if post['market'] else ''}{post['age']}: {post['text'][:70]}")
print(f"usage    {payload['usage']['tokens']} tokens today, about ${payload['usage']['cost']}")

said = briefing.spoken(payload)
print(f"\ninstruction to Gemini: {len(said)} characters\n{'-' * 60}\n{said[:900]}\n{'-' * 60}")

start = time.monotonic()
service = dataservice.DataService()
service.refresh(force=True)
snap = service.snapshot
print(f"data service refresh: {time.monotonic() - start:.1f}s | "
      f"{len(snap['market']['watchlist'])} stocks with sparklines, "
      f"{sum(len(v) for v in snap['news'].values())} headlines, "
      f"{len(snap['posts'])} posts, system {snap['system']}")

if "--speak" in sys.argv:
    import gemini_live
    live = gemini_live.LiveSession()
    live.start()
    print("speaking...", flush=True)
    t0 = time.monotonic()
    live.prompt(said)
    live.wait_for_audio(timeout=25)
    live.wait_until_quiet(timeout=120)
    print(f"spoken in {time.monotonic() - t0:.0f}s:\n{live.reply_text()}")
    live.close()
