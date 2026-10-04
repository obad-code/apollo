# Apollo

A voice assistant for your Windows PC - with a crew of agents that research,
analyse stocks, make YouTube Shorts and file work for Claude, all reported back
in one voice.

Hold `Ctrl+Alt` and speak - or press `Ctrl+1` once and just talk. Your voice
streams to Gemini Live and Apollo answers out loud. Speak Arabic and he answers
in Arabic.

```
  [Ctrl+Alt held]  ->  mic  ->  Gemini Live (audio in, audio out)  ->  Apollo's voice
   or always-on                  |
                                 |  tools (apps, sites, keys, media, volume,
                                 |  windows, reminders, markets, screen)
                                 |
                       Apollo decides who does what - your word wins
                                 |
     LYLA (research, accounts, downloads, YouTube Shorts) · THEIA (any idea:
     analysis, critique, best way) · MONEYPENNY (stocks, with the TradingAgents
     analyst team under her) · Q (files a GitHub ticket for Claude to build)
                                 |
                  each reports back - and Apollo says it, in his voice
```

---

## Quick start

| What | How |
|---|---|
| **Update Apollo** (and install what it needs) | Double-click **`update.bat`**, then close Apollo and open it again. |
| **Start Apollo** | Double-click **`start.bat`** (no console window). `install-startup.bat` starts it with Windows. |
| **Make one YouTube Short** | Double-click **`make-short.bat`**, or say "ليلى سوي مقطع". |
| **First time only** | An Anthropic API key - see [Step 1](#step-1--get-an-anthropic-api-key) below. |

Keys and passwords only ever go into Windows environment variables (`setx`),
never into a file in this folder.

---

## What Apollo does

**Mini Apollo** - a small bar at the top of the screen. At rest it shows his
mark; while you talk it shows what he says, a chart, a stock card. Start-up
status ("Starting up…", "System online") shows here too. It draws at your
screen's real resolution (`APOLLO_MINI_SCALE` forces a scale).

**The full display** (`` Ctrl+` ``) - modes: normal, clear, trading, agents,
expanded, OSIRIS; plus idle, edit, sound, away and hands-free.
- **Normal** - a HUD you arrange: the left roller (markets, projects, talks,
  reminders), news as picture stories, the crew's four tiles with health bars,
  LYLA's room.
- **Trading** - insiders, Congress, filings, market news, social chatter, and
  the counted verdict on each stock.
- **Agents** - four cards under Apollo. Open one to see its live steps; every
  result opens in a full-page **reader**: the whole report, a stock's full
  analysis, a Short's preview with Play.
- **Idle** - a retro green-tube TV where Apollo and the crew play little
  scenes (sofa, meeting, trading floor, LYLA's studio, campfire), or the two
  skies (event horizon, ember nebula). Back returns to Apollo.

**Market alerts** - news and price moves watched every minute. Decisive news
(a CEO thrown out, a trillion crossed, a takeover, a bankruptcy, a trading
halt) or a sharp move (8% in 15 minutes) on a stock you watch reaches you by
email headed **PULL!!** or **BUY!!**, and out loud if Apollo is up. Everyday
news stays quiet.

**Apollo improves himself.**
- **MONEYPENNY learns from her misses** - every call is graded a week later; a wrong one gets an honest
  post-mortem and a lesson she reads before every new call (`calls.py`).
- **Q's Fixes** - the **Fixes** button by the clock: once a day Q looks at the display and suggests three
  improvements in your style; *Send to Claude* files one as a GitHub issue, *Not my style* teaches him
  what you dislike, and *Point at something* lets you click anything and say what is wrong (`qfixes.py`).
- **THEIA reads your ideas** - every idea you save goes to her quietly; her analysis waits on the idea in
  the Ideas tab, Apollo mentions it once a day, and each morning's summary carries her three things for
  your day: an idea, a next step, or a question about your plans.

**YouTube Shorts** - LYLA makes one only when you ask. When it is ready
Apollo asks: post it, save it as a private draft, or keep the file. Nothing
is made or posted on its own unless you turn that on (`SHORTS_AUTO`,
`SHORTS_AUTOPOST`). Telegram can drive it from your phone (`telegram_bot.py`).
See `docs/shorts-playbook.md`.

### Apollo's crew

| Agent | Does | Ask like |
|---|---|---|
| **LYLA** | Research, sources, your connected accounts, YouTube downloads, **YouTube Shorts** | "ليلى سوي مقطع", "LYLA, any new mail from Ahmed?" |
| **THEIA** | The professor: any idea, in three passes - analysis, a hard critique, the best way - with a verdict | "ثيا حللي هالفكرة" |
| **MONEYPENNY** | Markets. On one stock she runs **[TradingAgents](https://github.com/TauricResearch/TradingAgents)** (Apache-2.0) - four analysts, a bull/bear debate, a trader and a risk team - and makes the final call over them. The whole team's notes are in the report. Without it installed, a built-in team in its shape runs and the report says so. `MONEYPENNY_TEAM=0` has her work alone. | "موني بيني وش رايك في انفيديا", "وش اسحب من اسهمي" |
| **Q** | Files what you want added or fixed as a GitHub issue for Claude to build | "قل لكلاود يضيف…" |

Apollo decides who does what, and your word wins: "انت حلل" means he does it
himself. Every result is also kept as a file in `Documents\Apollo\Crew`.

---

## Setting up the new parts

Everything below is optional: each part switches itself on when its key is
there, and says so plainly when it is not. In PowerShell, then open a new
terminal (`setx` only reaches terminals opened after it):

| For | Set | Where it comes from |
|---|---|---|
| Alerts by **email**, and "send an email" | `setx APOLLO_SMTP_USER "you@gmail.com"` and `setx APOLLO_SMTP_PASSWORD "xxxx xxxx xxxx xxxx"` | A Gmail **app password**: turn on 2-Step Verification, then <https://myaccount.google.com/apppasswords>. Optional: `APOLLO_ALERT_TO` (another address for alerts). |
| Alerts' **news** | `FINNHUB_API_KEY` (the live prices already use it) | <https://finnhub.io> - free. Google News is used too, with no key. |
| **Q** filing requests for Claude | `setx GITHUB_TOKEN "github_pat_..."` | GitHub → Settings → Developer settings → Fine-grained token, repository `obad-code/apollo`, **Issues: Read and write**. |
| **MONEYPENNY's TradingAgents** | `update.bat` installs it (needs Python 3.11+) | Uses your `GEMINI_API_KEY` (or `ANTHROPIC_API_KEY`). `TRADINGAGENTS_*` variables override its models. |
| **YouTube posting** | `Documents\Apollo\youtube_client.json` (an OAuth "Desktop app" client) | See `youtube_upload.py`. The first post opens your browser once. |
| **Telegram** | `APOLLO_TELEGRAM_TOKEN` and `APOLLO_TELEGRAM_CHAT` | From @BotFather. See `telegram_bot.py`. |
| **LYLA's downloads** | `.venv\Scripts\pip install yt-dlp`, and ffmpeg on PATH (`winget install ffmpeg`) | Without ffmpeg it still works, at a single-file quality. |
| **LYLA's connectors** (email, messages, calendar…) | `%LOCALAPPDATA%\Apollo\connectors.json` listing remote MCP servers | See `connectors.py`. Uses Claude (`ANTHROPIC_API_KEY`). |
| **THEIA's deep analysis** | `ANTHROPIC_API_KEY` | Without it, deep runs on Gemini Pro. |
| Pictures and screen reading | `GEMINI_API_KEY` (Apollo already has it) | - |
| The voice | `APOLLO_VOICE` (a Gemini voice name), `APOLLO_EXPRESSIVE=0`, `APOLLO_BARGE_IN` (0..1) | - |

---

## First-time setup

Apollo needs two keys, saved as Windows environment variables. In PowerShell,
then **close it and open a new one** (`setx` only reaches new terminals):

```powershell
setx GEMINI_API_KEY "..."          # Apollo's voice and most of his thinking - https://aistudio.google.com/apikey
setx ANTHROPIC_API_KEY "sk-ant-..." # checked at start-up; Claude for THEIA's deep runs and connectors
```

The Anthropic key comes from <https://console.anthropic.com/settings/keys> -
a separate thing from a Claude.ai subscription. If the key is identity-linked,
also set `ANTHROPIC_WORKSPACE_ID` (from the workspace's address bar,
`wrkspc_...`); a workspace the key does not belong to is dropped by itself.

Then double-click **`update.bat`** once (it installs everything), and
**`start.bat`** to run.

## Running it

Apollo starts once and stays running - nothing in the taskbar. To watch its
log instead: `.\.venv\Scripts\python.exe apollo.py`.

| Chord | Does |
|---|---|
| `Ctrl+Alt` (hold) | Talk. Hold, speak, release. |
| `Ctrl+1` | Always-listening on/off - talk without holding anything. |
| `` Ctrl+` `` | Open or close the full display. |
| `F2` | Arrange the normal display (the HUD editor). |
| `Ctrl+Alt+Shift+Q` | Quit (or the tray icon → *Quit Apollo*). `Esc` never quits. |

Running `start.bat` twice is harmless: the second copy sees the first and exits.
On a keyboard where AltGr types characters, AltGr *is* Ctrl+Alt - change
`HOTKEY` in `assistant.py` if that is you.

## The display

- **Mini Apollo** - the bar at the top edge. Native (GDI+ on a layered
  window), so it is truly transparent and never takes focus; the reason it is
  not HTML is in `docs/design-notes.md`.
- **Normal** - the clock with the **Summary** and **Fixes** buttons, the left roller (markets,
  talks, your projects with their boards, ideas, reminders), news as picture stories on the right,
  the crew's tiles, LYLA's room. Everything is movable with **Edit** / F2.
- **Clear** - only Apollo, big, in the middle.
- **Trading** - insiders, Congress, SEC 8-K filings, market-moving news,
  StockTwits and Reddit, and the counted verdict on each stock (`trading.py`).
- **Agents** - the four crew cards; every result opens in the reader.
- **Expanded** - every display as a tile you can move, resize and minimize.
- **OSIRIS** - the [OSIRIS](https://osirisai.live) intelligence map laid into
  the display, in its own window (`osiris.py`).
- **Idle** - after 10 minutes untouched, on asking (*"idle mode"*), or on
  Win+L: the retro TV or one of the two skies. Only **Back** wakes it.
- **Away** - *"I'm going out"*: the PC stays awake with Claude open.

## Stocks

- **Live prices** with a free `FINNHUB_API_KEY` (a WebSocket for the
  watchlist's US stocks); Yahoo Finance otherwise, every minute while New York
  trades.
- **The counted verdict** (`analysis.py`): STRONG BUY, BUY, HOLD, TRIM or
  AVOID from the business, valuation, trend and the analysts - with the green
  flags, the red flags, and why a call was held back (a price already above
  the analysts' target is never more than HOLD). A count of rules, not a
  prediction.
- **MONEYPENNY** runs TradingAgents on one stock and makes the call over it.
- **Her record** (`calls.py`): every call is kept with its price and graded a
  week and a month later - right if a BUY went up, an AVOID went down, a HOLD
  stayed within 5%. The hit rate is on the summary page.
- **Alerts** (`alerts.py`): decisive news or a sharp move on your stocks,
  emailed as **PULL!!** / **BUY!!** within a minute or two of the story.
- By voice: *"open Nvidia"*, *"add Palantir and AMD"*, *"take off Apple"*,
  *"when are Nvidia's earnings?"*, *"are Nvidia's insiders selling?"*.

## What Apollo can do

Gemini answers everything you say, in one voice, and decides from what you
asked; the tools are declared once in `tools.py`.

| Ask | What happens |
|---|---|
| *"Open Spotify"*, *"close Notepad"* | Opens or switches to the app; closing asks the app nicely, so unsaved work is safe. |
| *"Open YouTube"*, *"open my Downloads"* | Sites, files and folders. |
| *"Pause the music"*, *"volume to 30"* | Media keys and real volume control. |
| *"Snap Chrome left"*, *"type: see you at nine"* | Window control, typing and shortcuts - Arabic too. |
| *"Remind me in 20 minutes to stretch"* | Spoken when due, after any sentence in progress. |
| *"How's Nvidia?"*, *"chart Tesla for a month"* | The numbers the feed returned, with a chart in Mini Apollo. |
| *"Look at my screen"*, *"scan a file"* | One screenshot read when you ask; a file judged without being run. |
| *"Lock the PC"* | At once. Sleep, restart, shut down and sign out ask first. |
| *"ليلى سوي مقطع"*, *"موني بيني حللي AMD"* | A job for the crew - Apollo tells you when it is done. |
| Anything current | He searches rather than answering from memory. |

Screen clips are left to NVIDIA or the Xbox Game Bar.

## What Apollo knows

- **Your day** - watchlist and indices, headlines on what you follow, Trump's
  posts (market-moving ones flagged), Riyadh's weather and prayer times, the
  machine's load. Keyless feeds, kept fresh in the background
  (`dataservice.py`); a feed that is down shows its last answer and its age.
- **You** - a journal of your days on this PC only (`%LOCALAPPDATA%\Apollo\journal`,
  60 days) and a small profile of what you care about (`interests.py`), read
  at the start of every session. Delete both to make him forget.
- **Private Eye** - every three hours, the best fresh finds on your strongest
  interests, in the feed; mark them useful or not and it learns.
- **What it costs** - Apollo counts its own tokens (`usage.py`); the figures
  are estimates from the price table there.

## Settings

Everything is an environment variable (`setx NAME "value"`, then restart Apollo):

| Variable | What it does |
|---|---|
| `APOLLO_VOICE` | Gemini voice name (Puck by default). `APOLLO_EXPRESSIVE=0` for a flatter voice. |
| `APOLLO_MINI_SCALE` | Force Mini Apollo's resolution (1.5, 2…); by default it follows Windows' scaling. |
| `APOLLO_VSYNC=0` | Mini Apollo back on a plain timer instead of the screen's refresh. |
| `APOLLO_FULL_INTRO=1` | The old full-screen start-up screen instead of the status in Mini Apollo. |
| `APOLLO_ALERT_EVERY` | Seconds between alert checks (60). `APOLLO_ALERT_TO` sends alerts to another address. |
| `MONEYPENNY_TEAM=0` | MONEYPENNY works alone, without the analyst team. |
| `TRADINGAGENTS_*` | TradingAgents' own settings (models, debate rounds…). |
| `SHORTS_AUTO`, `SHORTS_AUTOPOST` | Daily Shorts on their own, and posting without asking - both off. |
| `SHORTS_WRITER=claude`, `SHORTS_VOICE_ENGINE`, `SHORTS_IMAGES`, `SHORTS_OBJECTS` | The Shorts' paid upgrades - see `docs/shorts-handoff.md`. |
| `APOLLO_TELEGRAM_VOICE` | The voice of Apollo's Telegram voice notes (an edge-tts voice name). |
| `CREW_MODEL`, `CREW_DEEP_MODEL`, `CREW_CLAUDE_MODEL`, `THEIA_CLAUDE_MODEL` | Which models the crew thinks with. |

The constants at the top of `apollo.py` (`AFK_SECONDS`, `ORB_PX`, `LINGER`…)
and `assistant.py` (`HOTKEY`, `CLAUDE_MODEL`…) are the rest.

## Files

| File | What it is |
|---|---|
| `assistant.py` | The engine: hotkey, mic, Whisper, routing, Claude, tools, TTS. Runs standalone in the console. |
| `gemini_live.py` | Apollo's voice. Owns the only microphone Apollo opens and streams it to Gemini's native-audio model, which answers in the Puck voice as audio rather than as text to be synthesised. Holds both listening modes. |
| `router.py` | Which backend answers this turn. One question: was an agent called by name? Everything else is conversation. |
| `agents.py` | The crew's names as you say them, in Arabic and English. A name says who should do the work; it never changes who speaks. |
| `crew.py` | THEIA, MONEYPENNY and Q, each a desk like LYLA's, and the board agents mode draws (`tests/test_crew.py`). |
| `alerts.py` / `emailer.py` | Market alerts: the news and price moves watched, scored, explained and told by email and voice (`tests/test_alerts.py`). |
| `connectors.py` | LYLA's reach into your own accounts, through remote MCP servers and Claude's MCP connector. |
| `github_requests.py` | Q's outbox: a request filed as a GitHub issue for Claude. |
| `youtube.py` | LYLA's downloads, through yt-dlp. |
| `memory.py` / `files.py` | What Apollo was told to remember and the day's talk; his own folder and the problem log. |
| `images.py` / `screen.py` | Pictures he draws; one screenshot, read when you ask about your screen. |
| `ui/full/explain.js` | The markup for visuals Apollo shows with an answer (charts, cards). |
| `ui/full/crewview.js`, `crewpage.js`, `wheel.js`, `widgetgrid.js`, `tiler.js` | Agents mode: the cards, each agent's live steps, and the parts of the dashboard (`tests/test_crew_board.py`). |
| `ui/full/optionwheel.js` | The left roller: the normal display's main menu. |
| `tools.py` | Every tool Apollo has, declared once for both Gemini and Claude, and the only place tool errors are caught. Also the confirmation rule for power actions. |
| `pc_control.py` | The Windows side of the tools: apps, sites, files, keyboard, media, volume, windows, power. Talks to Windows, never to a model. |
| `market.py` | Live prices, history, NYSE hours and TradingView links, from Yahoo Finance's public feed. |
| `feeds.py` | Headlines and posts, from keyless RSS feeds, cached and total. |
| `weather.py` | Riyadh's weather from Open-Meteo. |
| `sysinfo.py` | CPU, memory and the NVIDIA card, through NVML. |
| `usage.py` | The day's token ledger and an estimated cost. |
| `briefing.py` | What the recap contains, and whether today's has happened. |
| `dataservice.py` | The one background thread that keeps all of it fresh. |
| `clips.py` | Clip saving helpers. Recording itself is left to NVIDIA or the Xbox Game Bar. |
| `turnview.py` | What the overlay shows for the turn in progress, as your words, the reply and any chart arrive from different threads. |
| `presence.py` | When the full display is open (Ctrl+` is sticky), when Apollo is asleep on the idle screen and what wakes it (input, a voice, a conversation), and what a phase change does to the overlay. |
| `reminders.py` | Reminder storage and the watcher that fires them. |
| `probes/` | Live checks against the real APIs and PC: which Gemini model to use, transcript timing, and an end-to-end tool run. |
| `apollo.py` | The overlay host. Owns the window shapes, the tray icon, the presence watcher and the single-instance lock, and drives the page from `assistant`. |
| `displays.py` | Ultra mode's layout, kept: which displays are shown, where and how big, which one is expanded, the map's layers - and the words, in English and Arabic, that find each display by voice. |
| `osiris.py` | OSIRIS inside the display: the map's own window, laid over the frame the page leaves for it, owned by the display and gone whenever it goes. |
| `orb.py` | The overlay itself: the window, the states, and the composition - ring, panel, your words, the answer, cards and chart. |
| `overlay_paint.py` | Its paint box: the drifting CRT panel, the three-ring orb, the sparkle field and the horizon, each pre-rendered where a per-frame redraw would cost too much. |
| `overlay_state.py` | The springs and the state machine, with no window in sight. |
| `overlay_content.py` | What an answer actually contains and how tall that makes the overlay — reply parsing and layout, with no drawing code in it. |
| `ui/full/index.html` | The full display. Written by hand — edit it directly. |
| `ui/full/app.js` | Its panels, its bridge (`window.apollo.*`) and its motion. |
| `ui/full/app.css` | Its skin: the overlay's palette, the CRT surface, the grid. |
| `ui/full/shader.js` | The ground: an old set's slot mask lit by the CRT gradient, in plain WebGL. |
| `ui/full/globe.js` | Apollo's shape as data: the globe's meridians as it turns, its parallels, the star at its heart, and the easing of its pace. No DOM, so node tests it (`tests/test_globe.py`). |
| `ui/full/hud.js` | The normal display's HUD: the panels, cleaning a kept arrangement, snapping to the grid and to each other, resizing by a corner, the box a scaled panel needs, and the spring a drag rides on. No DOM, so node tests it (`tests/test_hud.py`). |
| `hud.py` | The HUD as you arranged it, kept - cleaned by the same rules as `hud.js` - and handed to the display as it opens. |
| `ui/full/tiles.js` | Ultra mode's rules: the displays, the default layout, moving, resizing, minimizing and expanding, and the line each says when minimized. No DOM, so node tests it (`tests/test_tiles.py`). |
| `ui/full/lyla.js` | LYLA, lifted out of the old page byte for byte. `tests/test_lyla_port.py` pins the two together. |
| `ui/full/lylaagent.js` | The crew's marks and LYLA's pipeline card, in plain JS and SVG (`tests/test_lyla_agent.py`). |
| `lyla.py` | LYLA's desk: the research Apollo hands her, on her own thread - what she reads, what she thinks with (Hermes or Gemini), her reports kept, and Apollo told when she is done (`tests/test_lyla_desk.py`). |
| `trading.py` | Trading mode's desk: insiders (OpenInsider), Congress, the SEC's 8-K filings, market-moving news, StockTwits and Reddit, X when it is set up, and the read of the next picks (`tests/test_trading.py`). |
| `ui/full/modes.js` | The display's modes - normal, clear, expanded, OSIRIS - and the switches to throw, in order, from one to another (`tests/test_modes.py`). |
| `ui/full/consolelights.js` | The consoles' readouts and eighteen lights, each something true: the sources, what Apollo is doing, the load, the uptime, the link and the heat (`tests/test_console_lights.py`). |
| `ui/full/feed.js` | The feed's rows, fuller: a source's initials for its tile, what a story is about, and the line over the list (`tests/test_feed_rows.py`). |
| `ui/full/sfx.js` | The display's sounds, synthesized with Web Audio: the recipes, and the player that keeps a sound from doubling up (`tests/test_sfx.py`). |
| `ui/fonts/thmanyah/` | Thmanyah Sans, as OTFs — what the overlay loads privately at runtime. |
| `ui/full/fonts/` | The same weights as WOFF2, under the page because pywebview's server roots there - and beside them IBM Plex Mono, Melete, Orbitron, VT323, and trading mode's Martian Mono, each with its licence. |
| `ui/legacy/index.html` | The old generated design, frozen. Nothing in the run reads it. |
| `build_ui.py` | Builds `ui/legacy/index.html` from the Claude Design export. **Not part of the run.** |
| `ADD A CITY.dc.html` | The old design source, as exported from the canvas. |
| `trading_team.py` | MONEYPENNY's analyst team: the real TradingAgents when installed, and a built-in team in its shape otherwise (`tests/test_trading_team.py`). |
| `analysis.py` | A stock's counted verdict (STRONG BUY … AVOID), the green and red flags, and why a call was held back. |
| `shorts.py` and `shorts_*.py` | LYLA's Shorts: the script, the hero and scenes, sound, optional Gemini pictures and objects, the render. |
| `autopost.py` / `youtube_upload.py` / `telegram_bot.py` | What happens to a finished Short (post, private draft, keep), the upload, and the phone remote. |
| `niche.py` | LYLA's niche research for the channel. |
| `watch.py` | A contact sheet and report of any video or link, for sending to Claude. |
| `myprojects.py` / `ui/full/board.js` | Your projects, each with a Freeform-style board, and THEIA's notes on them. |
| `ui/full/crttv.js` | The idle screen's retro TV and its scenes. |
| `ui/full/idlescenes.js`, `embers.js` | The idle screen's two skies, and the embers over them. |
| `update.bat` / `make-short.bat` | One double-click to update; one to make a Short. |
| `docs/design-refs/` | The reference pictures and sketches the designs were built from. |
| `docs/shorts-playbook.md`, `docs/shorts-handoff.md` | How the Shorts are made, and the paid upgrades. |
| `docs/design-notes.md` | The long-form design notes and history (archive). |
| `digest.py` / `ui/full/digest.js` | Your summary: what goes on it, when it is made, and the page. |
| `calls.py` | MONEYPENNY's record: every call kept, graded at a week and a month, and her lessons from the wrong ones. |
| `qfixes.py` / `ui/full/fixes.js` | Q's fixes for the display: the daily look, your taste, and pointing at something. |
| `start.bat` | Double-click launcher. Runs `pythonw.exe`, so there is no console window. |
| `install-startup.bat` | Adds Apollo to Windows startup. `uninstall-startup.bat` removes it. |
| `voices/` | A downloaded fallback voice, only used when the others are down. Delete it and it re-downloads. |
| `.venv/` | The virtual environment |

## Changing the display

Edit `ui/full/` directly - plain ES modules, no build step. To look at it
without Apollo, serve `ui/` (`python -m http.server 8765 --directory ui`) and
open `full/index.html`. Anything the page uses must live under `ui/full/`:
pywebview roots its server there, and `tests/test_page_assets.py` fails on a
reference that climbs out.

## The typeface

Apollo is set in **Inter** (Latin) and **IBM Plex Sans Arabic** (Arabic) -
the open faces closest to Apple's SF Pro and SF Arabic, which may not be
shipped inside an app. Both are under the SIL Open Font License and travel
with the code: `ui/fonts/` for Mini Apollo (GDI+), `ui/full/fonts/` for the
display. A few faces stay for their one job: Orbitron (the idle LED sign),
VT323 (the old boot tube), Melete (the neon name) and Martian Mono (the
trading desk's figures).

## Troubleshooting

| Problem | Fix |
|---|---|
| `ANTHROPIC_API_KEY is not set` | Open a **new** terminal after `setx`. |
| Claude answers 404 / workspace errors | Check `ANTHROPIC_WORKSPACE_ID`; a wrong one is dropped automatically on the next start. |
| Gemini `429 RESOURCE_EXHAUSTED` | The free tier's daily quota is used up (pictures run out first). It resets daily, or enable billing on the key. |
| Gemini `503 UNAVAILABLE` | Google is busy - Apollo tries the next model; try again in a minute. |
| `update.bat` fails on TradingAgents | It needs Python 3.11+. Everything else still installs; MONEYPENNY uses her built-in team and says so. |
| Apollo answers in text but no sound | Check Windows' output device (`APOLLO_OUTPUT_DEVICE` picks another). |
| The hotkey does nothing | A remapping tool may hold Ctrl+Alt, or an Administrator window has focus. |
| A Short fails | The error names the step; `make-short.bat` shows the whole message. |
| No alert emails | Check `APOLLO_SMTP_USER` / `APOLLO_SMTP_PASSWORD` (a Gmail **app password**). |

## Cost

- **Gemini** - the voice, LYLA, alerts, the summary's news and the Telegram
  chat. The free tier covers everyday use; pictures and heavy days can hit its
  limits.
- **TradingAgents** - one stock is about a dozen model calls (a few minutes):
  the heaviest everyday thing. `MONEYPENNY_TEAM=0` turns it off.
- **Claude** - only where you set it up (THEIA's deep runs, connectors,
  `SHORTS_WRITER=claude`). Watch spend at <https://console.anthropic.com/settings/usage>.
- **Everything else** - live prices (Finnhub), news, weather, Telegram,
  edge-tts voices - is free.

---

The long-form design notes - how each part was built, the measurements behind
the choices, and the history - are in [`docs/design-notes.md`](docs/design-notes.md).
