# Apollo, fully developed — design spec

Date: 2026-09-19 · Status: awaiting your review

Apollo becomes an assistant that *does* things: it controls the PC by voice,
pulls live market data and news, keeps a replay buffer of the screen, briefs
you once a day, and gets two redesigned faces — a minimized overlay built from
your three HTML designs and the sparkles component, and a full display built
around the shader animation.

---

## 1. What was agreed

| Topic | Decision | Source |
|---|---|---|
| How Apollo acts | Gemini Live gets the tools directly (approach A). One voice, one turn. | You |
| Language | Match whatever you speak — Arabic or English. Arabic lays out right-to-left. | You |
| Watchlist | AAPL, MSFT, NVDA, TSLA, AMZN, GOOGL, META, S&P 500, Nasdaq | You |
| News interests | Marvel, GTA 6, PlayStation, gaming, movies, plus markets | You |
| Posts | Trump's Truth Social posts, market-moving ones flagged | You |
| Stock charts | Apollo draws them; "open it in TradingView" opens the browser chart | You |
| Daily recap | Automatically once a day (first time you're at the PC), and on demand ("brief me") | You |
| Minimized overlay | Your Main / Expanded / ReplyChart designs + sparkles component, minimal: no gold outline, dim drifting violet/teal CRT gradient, three-ring "searching" orb | You (mockup v5) |
| Full display | Shader background, clock/date/Hijri/weather, markets, headlines, posts, usage, system, LYLA's room kept | You (mockup + "keep LYLA") |
| Weather city | Riyadh | You |
| Ctrl+` | Stays open until pressed again | You |
| Clips | Last 60 s of the whole desktop, GPU-encoded, saved to `Videos\Apollo's Clips` | You + my recommendation |
| Stack | Stay on Python + pywebview. The React/shadcn/Tailwind instructions are not applicable; both effects are rebuilt natively (shader in plain WebGL, sparkles on canvas). | My call |
| Data sources | Free, keyless: Yahoo Finance chart feed (Stooq backup), Google News RSS, trumpstruth.org RSS, Open-Meteo | My call |

---

## 2. Audit — what is broken today

| # | Problem | Root cause | Fixed in |
|---|---|---|---|
| A1 | Ctrl+1 plays the HUD chime ~4×/second | `run_loop` calls `ui.status(LISTENING)` after every 250 ms poll in always-listening (`assistant.py:1696`); the page chimes on every `status('Listening')` (`ui/index.html:3186`) | P1 |
| A2 | Answers vanish ~¼ s after appearing in always-listening | Same repeated `LISTENING` → `Apollo.on_status` calls `orb.clear_content()` each time (`apollo.py:811`) | P1 |
| A3 | "Open Chrome" doesn't open Chrome | Normal turns go to Gemini Live, which has no tools; only a named agent reaches Claude's `control_pc` | P2 |
| A4 | Current questions (news, prices) are answered from memory | Gemini Live has no search tool configured | P2 |
| A5 | Normal answers never carry a chart | Only the agent path runs `overlay_content.split_reply` | P2 |
| A6 | Arabic speech transcribes as garbage | Whisper model is `base.en` (English only) | P2 |
| A7 | Ctrl+` closes on the next keypress/mouse move | `check_presence` closes a hand-opened display on input | P1 |
| A8 | Full display numbers are fake | Telemetry panels are canvas demo animations | P6 |
| A9 | Voice model is a Sept-2025 preview | `gemini-2.5-flash-native-audio-preview-09-2025`; `gemini-3.8-live` is available on this key | P2 |
| A10 | Reminders exist but can't be used | `reminders.py` is never imported | P2 |
| A11 | Tray says "hold Ctrl+Space to talk" | Stale label (`apollo.py:461`) | P1 |
| A12 | README repeats "Why not a true wallpaper?" | Duplicate section | P1 |

---

## 3. Architecture

One Python process, as today. New modules are small and single-purpose; each
can be tested without a screen or a microphone.

```
apollo.py (host: windows, hotkeys, presence, tray)
 ├─ assistant.py        run loop, reporters, Claude (agents only)
 ├─ gemini_live.py      the voice; now with tools + Google Search
 │    └─ tools.py       ONE registry: declarations for Gemini AND Claude, handlers
 │         ├─ pc_control.py   apps, files, URLs, media, volume, windows, keys, power
 │         ├─ market.py       quotes + series (Yahoo → Stooq), NYSE clock
 │         ├─ feeds.py        Google News RSS, trumpstruth RSS, market-moving flag
 │         ├─ weather.py      Open-Meteo (Riyadh)
 │         ├─ briefing.py     composes the daily recap; once-a-day state
 │         ├─ clips.py        GPU replay buffer + save
 │         └─ reminders.py    (existing, now wired)
 ├─ dataservice.py      background refresh of market/feeds/weather/system/usage → snapshot
 ├─ usage.py            per-day token + cost ledger (Gemini + Claude)
 ├─ orb.py              native resting ring (unchanged look) + fallback overlay renderer
 ├─ overlay window      NEW: minimized overlay (HTML if the spike passes)  ui/overlay/
 └─ full display        REBUILT: hand-authored page                         ui/full/
```

### Threads
Unchanged: UI thread (pywebview/WinForms), watcher, worker (`run_loop`),
Gemini loop thread. New: **tool executor** (a small thread pool — tools never
run on the Gemini event loop), **data service** (timed refreshes), **replay
buffer** (capture + encode).

### One turn, end to end (approach A)
1. You hold Ctrl+Alt (or talk, in always-listening). Audio streams to Gemini.
2. Gemini's *input transcription* streams your words → overlay shows them live,
   in your language.
3. Gemini decides to call a tool, e.g. `show_stock_chart{symbol:"NVDA"}`.
4. `gemini_live` hands the call to the executor → `tools.run()` → handler →
   result dict. The overlay's status line narrates it (`SEARCHING › NVDA`).
   Handlers that produce something to look at push it straight to the overlay
   (`ui.visual(...)`), so charts always come from real data, never from prose.
5. The result goes back with `send_tool_response`; Gemini speaks the answer in
   Puck's voice, in the language you used.
6. Named agents still route to Claude, which receives the *same* tools from the
   same registry (plus web search and deep research).

---

## 4. Sub-projects, in build order

Each ends with its own verification before the next starts.

### P1 — Fix pack
- **Status dedupe (A1, A2).** `WebReporter.status` drops a state identical to
  the last one it reported. `run_loop` reports `LISTENING` only on transitions.
  `Apollo.on_status` clears the overlay only on a transition *into* listening.
  The page chimes only when the phase actually changes (defence in depth).
- **Always-listening linger.** A reply shown in always-listening collapses
  `LINGER` seconds after its audio finishes, not on the next poll.
- **Sticky Ctrl+` (A7).** A hand-opened display stays until Ctrl+` again. The
  AFK-opened display still closes on your first input.
- **Tray label (A11), README duplicate (A12).**
- Verify: instrumented chime counter = 1 per Ctrl+1 press over 10 s; an
  always-listening reply stays on screen ≥ LINGER; Ctrl+` survives typing.

### P2 — Apollo's hands
- **`tools.py`** — each tool is `name, description, JSON schema, handler,
  confirm, visual`. Exports `gemini_declarations()`, `claude_tools()`,
  `run(name, args, ctx) → dict`. Every handler returns a dict and never raises
  (errors come back as `{"ok": false, "error": "..."}` for the model to speak).
- **Tool list**

  | Group | Tools |
  |---|---|
  | Apps & files | `open_app`, `close_app`, `open_url` (sites by name or URL), `open_path` (file/folder) |
  | Control | `media` (play/pause/next/previous), `volume` (set/up/down/mute), `window` (minimize/maximize/restore/close/focus/snap left/right/show desktop), `type_text`, `press_keys` |
  | Power | `system_power` (lock/sleep/restart/shutdown/sign out) — **confirm** |
  | Reminders | `set_reminder`, `list_reminders`, `cancel_reminder` |
  | Markets | `stock_quote`, `show_stock_chart` (1d/5d/1mo/6mo/1y/5y), `open_tradingview` |
  | Knowledge | Google Search (built-in), `get_news(topic)`, `get_posts(hours)` |
  | Apollo | `daily_briefing`, `save_clip(seconds)`, `show_display(open/close)` |

- **Confirmation guard.** Tools marked *confirm* (`system_power`) refuse
  unless called with `confirmed: true` **and** you have spoken since Apollo
  asked — so the model can't approve its own request inside one turn.
  `close_app` never force-kills: it sends a normal close, so the app itself
  asks about unsaved work.
- **`gemini_live.py`** — config gains `tools=[{function_declarations}, {google_search}]`
  and `input_audio_transcription` in both modes. The receive loop handles
  `tool_call` (dispatch to executor, reply via `send_tool_response`) and
  `tool_call_cancellation`. New callbacks: `on_heard` (live partials),
  `on_tool(name, phase)`.
- **Model upgrade.** Candidates in order: `gemini-3.8-live`,
  `gemini-2.5-flash-native-audio-latest`, the current preview. A probe script
  checks each for: connects, Puck voice, manual activity start/end, both
  transcriptions, a function-call round trip, Google Search. First to pass all
  checks is used; failure of the chosen model at runtime falls back down the
  list.
- **Transcription.** Gemini's input transcription is the primary transcript
  (overlay text + agent-name routing), multilingual. Whisper switches from
  `base.en` to multilingual `small` and is only used if Gemini's transcript
  hasn't arrived 1.5 s after you release the chord. If the probe shows Gemini's
  transcript does not stream *while* you hold the chord, Whisper keeps
  producing the live partials (multilingual model).
- **System instruction** gains: reply in the user's language and dialect; use
  tools for actions and live data rather than guessing; confirm actions in one
  short sentence; never read URLs; never invent numbers.
- **Visuals from tools.** `stock_quote` / `show_stock_chart` / `get_news` etc.
  push `{"kind": "chart"|"cards"|"list", ...}` to the overlay directly.
- Verify: unit tests for every handler's argument validation and the confirm
  guard; probe: "open notepad" opens Notepad, "what's NVDA at" returns a
  number matching the feed, "close notepad" asks first.

### P3 — Clips
- **`clips.py` `ReplayBuffer`**: `ddagrab` (desktop duplication, GPU) →
  `scale_d3d11` to 1920×1080 → `hwdownload` → `h264_nvenc` (CQ ~23, 30 fps,
  1-second keyframes) → encoded packets kept in a 60-second ring in RAM
  (~70–100 MB). If the GPU graph fails, fall back to `gdigrab` + `h264_nvenc`,
  then `libx264 ultrafast`.
- **System audio** via WASAPI loopback, encoded to AAC alongside. Mic is not
  recorded.
- **Save**: from the keyframe at/just before *now − N s* to *now* → MP4
  (faststart) at `%USERPROFILE%\Videos\Apollo's Clips\Apollo 2026-09-19 21-14-07.mp4`,
  written on a background thread. Overlay shows a `CLIP · 60s saved` card;
  "open my clips" opens the folder.
- Nothing is ever written to disk unless you ask. Tray gets a "Replay buffer:
  on/off" toggle.
- Verify: save a 10 s and a 60 s clip; `av.open` reports the right duration
  (±1 s), video and audio streams present; CPU cost of the running buffer
  measured and recorded.

### P4 — Data and the daily recap
- **`market.py`**: Yahoo chart endpoint for quotes + series (1d@5m, 5d@30m,
  1mo+@1d), Stooq CSV as backup; NYSE open/close times via `zoneinfo`
  (needs `tzdata`); cache 60 s while the market is open, 15 min otherwise.
- **`feeds.py`**: Google News RSS per topic — Gaming (`PlayStation OR "GTA 6"
  OR gaming`), Marvel, Movies, Markets; trumpstruth.org RSS for posts; parsed
  with the standard library; cache 10 min (posts 5 min). *Market-moving* flag:
  keyword list (tariff, Fed, rates, China, trade, sanctions, oil, crypto, and
  the watchlist's names/tickers).
- **`weather.py`**: Open-Meteo current + today's high/low for Riyadh.
- **`usage.py`**: per-day ledger in `%LOCALAPPDATA%\Apollo\usage.json`, fed by
  Gemini `usage_metadata` and Claude `usage`; cost from an editable price table.
- **System stats**: CPU and RAM via `psutil`, GPU via NVML.
- **`dataservice.py`**: refreshes on those schedules, keeps the latest
  snapshot for tools, pushes it to the full display while it's visible.
- **`briefing.py`**: `compose()` → date (Gregorian + Hijri), weather, index +
  watchlist movers, top 1–2 headlines per interest, posts from the last 24 h
  (market-moving first), today's reminders.
- **Once a day**: state file holds the last briefing date. When today's
  hasn't happened and you become active (input after ≥ 10 min idle, or Apollo's
  startup at sign-in) and no turn is in progress, Apollo opens the full display
  and asks Gemini to call `daily_briefing` and speak it (~30–45 s, in the last
  language you used). "Brief me" does the same any time.
- Verify: parsers tested on saved fixtures (including malformed feeds); live
  fetch probe for every source; once-a-day logic tested with a fake clock.

### P5 — Minimized overlay (your HTML + sparkles)
- **Step 0 — transparency spike (≤ 45 min).** A second pywebview window with
  `DwmEnableBlurBehindWindow` (empty region) + click-through styles. Passes if
  (1) the desktop shows through everywhere the page is transparent, (2) soft
  alpha (glow) blends correctly, (3) clicks pass through, (4) focus is never
  taken, (5) CSS animation holds 60 fps. **Pass →** the overlay is an HTML page
  (`ui/overlay/`). **Fail →** the same design drawn natively in `orb.py`
  (sparkles capped at ~80 particles to hold 60 fps).
- **Resting state**: the existing native amber ring, unchanged.
- **States** (as in mockup v5): Listening (panel drops, cyan live transcript,
  thin caret), Searching (orb spins ~5×, status narrates tool steps), Result
  (panel grows, borderless glass cards stagger in), Chart reply (gradient
  sheet, reply centred, RTL for Arabic, violet→cyan→amber line draws on, fill
  fades in, last dot pulses), collapse `LINGER` s after speech.
- **Look**: no gold outline; minimal type (one face, three sizes); dim violet
  / teal / rose gradient clouds drifting on 16 / 21 / 26 s loops over deep
  navy; faint scanlines; three-ring orb (amber, amber, cyan); horizon of three
  hairlines (blurred, thin, bright short core) + ~400 multicolour sparkles in a
  dome, reacting to your voice.
- **Motion**: no-bounce springs for size/position, interruptible (re-targets
  mid-flight); exits ~300 ms, entries ~500 ms; text rises 6 px with a fade;
  cards stagger 60 ms; numbers roll; everything falls back to fades when
  Windows animation effects are off.
- **Bridge**: `window.overlay.update({state, you, reply, visual, activity,
  lang})`; voice level throttled to ~15 Hz and smoothed in the page.
- Verify: screenshot of every state on the real desktop; frame-time trace
  during listening; Arabic reply renders RTL.

### P6 — Full display
- **New hand-authored page** `ui/full/` (`index.html`, `app.css`, `app.js`,
  `shader.js`, `lyla.js`) replacing the generated one; the old page is kept as
  `ui/legacy/`. `build_ui.py` is retired for the full display.
- **Layout** (as in the part-3 mockup): shader background (your ring shader,
  tinted violet/amber/teal, dimmed, half resolution, vignette + scanlines);
  top-left clock with seconds, date, day-of-year · week · Hijri, weather
  (Riyadh); top-right live status dots (Gemini, Claude, mic) + NYSE countdown;
  left Markets (indices large, 7 rows with sparkline/price/change); right
  Headlines (topic chips, rotating) and Trump posts (market-moving flagged);
  bottom strip tokens/cost today · CPU/GPU/RAM · clips; centre orb + wordmark;
  **LYLA's room kept**, ported from the current design into its own module
  and placed along the bottom above the status strip.
- **Behaviour**: opening choreography (panels rise with stagger, sparklines
  draw, numbers count up); live price change flashes green/red; while Apollo
  answers the panels dim, the orb lifts and shrinks, the answer and any chart
  take the centre; shader ripples faster while Apollo speaks. Rendering pauses
  when hidden.
- **Motion library**: Motion (motion.dev), vendored locally in `ui/vendor/`
  so the display works offline.
- **Bridge**: `window.apollo.{status, turn, note, fatal, mode, data, visual,
  level, briefing}`.
- Verify: screenshots idle / answering / briefing at 2560×1440; shader frame
  time; every panel shows live values matching the data service snapshot.

---

## 5. Error handling

- A tool never raises into the conversation; failures are spoken briefly.
- A dead data source shows its last good value with an age ("12m ago"), then a
  dash — never a made-up number.
- A failed model/session falls back down the model list and says so once.
- Replay buffer failure disables clips and says why; Apollo keeps running.
- The overlay and full display are cosmetic: an exception there is logged and
  never stops a turn.

## 6. Testing

- `tests/` with pytest: tool validation + confirm guard, status dedupe,
  market/feeds/weather parsers on fixtures, briefing composition, once-a-day
  logic, clip ring trimming (synthetic packets), overlay layout.
- `probes/`: live checks that need network, the GPU or a microphone (model
  capability matrix, feed fetches, 10 s clip). Run by hand, results recorded.
- Visual checks: real-desktop screenshots of every overlay state and the full
  display, compared against the approved mockups.

## 7. New dependencies (need your OK to install)

| Package | Why |
|---|---|
| `pytest` | tests |
| `tzdata` | NYSE hours — Windows Python has no time-zone database |
| `psutil` | CPU / RAM for the dashboard |
| `pycaw` | precise volume control |
| `PyAudioWPatch` | system-audio loopback for clips |
| `motion` (JS, vendored file) | springs and animation on both pages |

## 8. Safety net

The project folder is not under version control. Before any code changes,
initialise a local git repository (no remote) and commit the current state,
so every step can be reverted.

## 9. Risks

| Risk | Fallback |
|---|---|
| `gemini-3.8-live` rejects manual activity detection or Puck | next model in the list |
| Transparent WebView2 spike fails | native overlay renderer |
| Yahoo blocks requests | Stooq backup; values marked stale |
| trumpstruth.org down | posts panel shows last fetch time |
| GPU capture graph unavailable | gdigrab path; clip still works at higher CPU |
