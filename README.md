# apollo

ai assistant - a voice assistant for your Windows PC.


Hold `Ctrl+Alt` and speak — or press `Ctrl+1` once and just talk. Your voice
streams to Gemini Live and Apollo answers out loud in Puck's voice.

```
  [Ctrl+Alt held]  ->  mic  ->  Gemini Live (audio in, audio out)  ->  Puck
   or always-on                  |        |        \
                                 |     tools     Google Search
                                 |   (tools.py: apps, sites, keys, media,
                                 |    volume, windows, reminders, markets)
                                 |
                  its transcript of you  ->  was an agent called by name?
                                                          |
                                             LYLA / ATLAS / ECHO / NOVA /
                                             THE WORKSHOP / OPTIMO / HERMES
                                                          |
                                     Claude API (same tools)  ->  Fish Audio
```

**One assistant, one voice.** Everything you say — chat, a quick command, a
question about your own code — is answered by Gemini in Puck's voice. Claude
still has the tools, but it belongs to the seven agents now and answers only
when you call one by name. See [One voice, and the door Claude is behind](#one-voice-and-the-door-claude-is-behind).

Your *audio* goes to Google while you speak, and an agent's reply text goes to
Anthropic and to Fish Audio. A local Whisper is kept only as a backup
transcriber.

It does more than answer questions, and it does it in the same voice: ask it
to open Chrome and it opens Chrome; ask how Nvidia did this week and it draws
the chart; ask what's new with GTA 6 and it searches. Speak Arabic and it
answers in Arabic. See [What it can do](#what-it-can-do).

---

## Step 1 — Get an Anthropic API key

You need a key from the **Anthropic Console**. This is a separate thing from a
Claude.ai chat subscription; a Pro/Max plan does *not* include API credit.

1. Go to <https://console.anthropic.com> and sign up (or log in).
2. Add credit under **Billing**. The minimum is $5, and it does not expire.
   That is a lot of voice assistant — see the cost note at the bottom.
3. Go to **Settings -> API keys**: <https://console.anthropic.com/settings/keys>
4. Click **Create Key**, name it something like `voice-assistant`, and copy it.
   It looks like `sk-ant-api03-...`.

   **Copy it now.** The console will never show you the full key again. If you
   lose it, just delete that key and make a new one — no harm done.

## Step 2 — Save the key so the app can find it

In PowerShell:

```powershell
setx ANTHROPIC_API_KEY "sk-ant-api03-paste-your-key-here"
```

Then **close that terminal and open a new one**. `setx` only affects terminals
opened *after* it runs, which trips up almost everyone the first time.

Verify it took:

```powershell
$env:ANTHROPIC_API_KEY.Substring(0,14)
```

You should see `sk-ant-api03-a` or similar. If you get an error, the variable
isn't set in this terminal — check that you opened a new one.

> The key lives in your Windows user environment, not in this folder, so it
> won't get committed to git or copied around by accident.

## Step 2b — Set your workspace ID (identity-linked keys only)

**Your key needs this.** Identity-linked API keys must state which workspace
each request acts in, otherwise every call fails with a 400:

```
anthropic-workspace-id is required when authenticating with an
identity-linked API key
```

1. Go to <https://console.anthropic.com/settings/workspaces>
2. Open your workspace. The ID is in the address bar — it looks like
   `wrkspc_01AbCdEf...`
3. Set it, then open a new terminal:

```powershell
setx ANTHROPIC_WORKSPACE_ID "wrkspc_01AbCdEf..."
```

The app reads this and sends it as the `anthropic-workspace-id` header on every
request. If your key is a plain (non-identity-linked) one, leave this unset and
the header is simply omitted.

## Step 3 — Run it

Double-click `start.bat`. Apollo starts once and then stays running: there is
no window to open and close, and nothing appears in the taskbar.

```powershell
.\.venv\Scripts\python.exe apollo.py    # same thing, with a console to watch
```

To have it start with Windows, double-click `install-startup.bat` once. It
drops a shortcut in your Startup folder that launches Apollo silently at
sign-in, and starts it immediately. `uninstall-startup.bat` undoes it.

### What you see

Apollo has two windows, and it is only ever as big as what it needs to show.

| Shape | When | Covers |
|---|---|---|
| **Overlay** | at rest, and for a whole conversation | a mesh at the top edge (~1% of the screen), growing downward only as far as the answer needs |
| **Full** | you pressed `` Ctrl+` ``, or you have been away 10 min (the idle screen) | the whole work area |

At rest it is just the mesh: a small, fine ring of little yellow points,
turning slowly, hanging off the very top edge of the screen with only its
bottom quarter in view. It is genuinely transparent — your wallpaper and
desktop icons show through it and through its glow, because it is drawn with
real per-pixel alpha rather than being an HTML page in a rectangle (see
[below](#why-the-overlay-is-not-html)). It never takes focus either, so your caret
stays where you left it, and clicks pass straight through.

Hold `Ctrl+Alt` from **any** application, say *"What's Nvidia doing?"*, and
release. Everything that follows happens in a panel that drops from the top
edge of the screen and retracts when it is done:

| | What you see |
|---|---|
| **At rest** | A small ring of little amber points, hanging off the top edge with a quarter of it in view - only the points: no lines between them and no glow round them, each one plain round light, twinkling a little and turning together, slowly. Your wallpaper shows through everything else. |
| **While you talk** | The card drops down, in the full display's own style: black glass with the display's CRT gradient drifting along its foot - warm on the left, cool on the right - inside an amber hairline, Apollo as the display draws him (a small globe with the star at its heart) and APOLLO beside him, your words as they are transcribed, and a word saying it is listening. Under the card's edge, a glowing horizon and a dome of sparkles that brighten and speed up with your voice. |
| **While it works** | The globe spins up, and the line under your words says what it is doing - *searching the web*, *fetching NVDA*, *saving the clip*. |
| **When it answers** | The reply in warm white, each word rising out of a blur. An answer that rests on real numbers brings a chart with it - violet into cyan into amber, with the last reading marked - and one that is two to six figures brings borderless cards instead. |
| **Afterwards** | It retracts into the ring, quicker than it came. |

Arabic answers are laid out right to left, in the same Thmanyah face as
English. The panel is black glass hanging from the top edge, a quarter of it
above the screen: a yellow CRT glow - straw to ember - drifts along its foot
on loops of nine to thirteen seconds, over printed dots and scanlines, so it
never sits still and never repeats.

```
      .  .                   resting - the ring of points alone
       |   Ctrl+Alt (hold)
       v
    +--------------+         listening - your words in cyan, the orb turning,
    | (o)  words   |           sparkles under the panel's edge
    +--------------+
       |
       v
    +--------------+         searching - the orb spins up and the line
    | (O)  words   |           underneath says what it is doing
    |  searching   |
    +--------------+
       |
       v
    +--------------+         answering - the reply in amber, with a chart
    | (o)  words   |           or a row of cards if the answer has figures
    |  the answer  |
    |  [ chart ]   |
    +--------------+
       |
       v   ~4s after it stops
      /\/\                   back to resting
```

**Why it is drawn by hand.** The panel is not a web page. A WebView2 window
here cannot be made see-through: its own background colour, the blur-behind
trick that winit and tao use, the layered style and click-through were each
applied in turn and together, and the desktop behind the window still changed
in 81% of pixels (`probes/probe_transparent_matrix.py`). So the overlay is
GDI+ on a layered window, which is the one path on Windows to real per-pixel
alpha. A frame costs about 4.5 ms of the 16.7 ms a 60 fps frame has, because
everything that does not change shape - the panel's gradient, the drifting
light, the orb's glowing points, the sparkle field - is rendered once and
blitted (`probes/probe_overlay_frames.py`).

**Where a chart comes from.** Not from guessing at the prose: Apollo's market
tools draw what they fetched, and a reply can carry one machine-readable line
that is stripped before it is spoken (`overlay_content.py`). Every number in
one is a number Apollo actually has.

### The full display

**Apollo's shape and its name.** On the full display Apollo is a globe,
the way a wireframe icon draws one, with a star of light at its heart: a
wide outline, meridians pole to pole as narrower ellipses inside it,
parallels straight across, and in the middle a four-pointed star, all in
warm white over a warm glow (`ui/full/globe.js` has the lines). It turns
about its upright axis, so the meridians widen and narrow as they come
round, their near halves bright and their far halves faint behind them,
and the star breathes with your voice. While Apollo works the globe
brightens and turns faster and a wave goes out from the star; listening,
the lines take a gradient, cyan in the middle to orange at the edge;
speaking, the star grows and a white bloom lifts off it. Under it
the name is a neon sign: Melete, 19px, spaced a fifth of a letter apart, in
#FFF0CE, each letter pulsing on its own a little after the one before, the
first O a tube on its way out, a warm bloom breathing behind and three dots
running under it. It stands aside while Apollo is busy. Melete is under the
SIL Open Font License (`ui/full/fonts/melete/OFL.txt`).

On the idle screen and in the intro the name is an LED sign on an old tube
instead: Orbitron at its heaviest, upright and drawn a little taller than it
comes, with room between the letters, used as a stencil over a grid of small
lit cells, with a bloom, the three colours landing a hair apart, a flicker,
scanlines and now and then a bright band rolling down (`ui/full/ledword.js`) -
and all of it seen through the same fisheye as the picture behind, its colours
parting towards the edges. It arrives scrambled, like the scramble-text
component: every letter a random symbol, settling into the word from the
left. Orbitron is under the SIL Open Font License
(`ui/full/fonts/orbitron/OFL.txt`), so unlike Thmanyah it may be shared
with the code.

**The type and the colour.** Everything else on the display - the labels,
the lists, the buttons, the clock - is set in IBM Plex Mono (200 to 600,
SIL Open Font License, `ui/full/fonts/ibm-plex-mono/`), with Thmanyah behind
it for Arabic, in amber on black: #FFB000, #FFC15E, #FFD48A and #FFF0CE,
every word with a warm orange glow.

**The intro.** As Apollo starts, the display holds the screen for about
three and a half seconds (`INTRO_SECONDS`) and boots like an old machine
on a green tube (`ui/full/boot.js`): the tube opens out of a bright line,
its checks type themselves out top left in VT323 - memory, voice link,
market feed, Private Eye, neural core - the name settles out of its
scramble in green phosphor, `> SYSTEM ONLINE` types under it, and then the
boot screen blurs away while the display comes up into focus under it - and
the display stays open, as if Ctrl+` had been pressed; Ctrl+` puts it away.
It is skipped when a full-screen program was already up, so a game or a
film is left alone and Apollo stays in the overlay.

The full display is the whole screen. Behind everything, an old set's own
pixels (`ui/full/shader.js`): a slot mask as fine as a TV's - cells of a red,
a green and a blue slot, six screen pixels across, laid on lightly - lit by
a CRT gradient: one wide band of light leaning across the tube from the top
left to the bottom right, warm below it (red, orange, yellow), pale along its
ridge and cool above it (teal, blue, night), with soft scanlines and faint
wavy ripples crawling up the glass - bulged by a fisheye, and breathing
rather than flickering. The gradient flows, and fast: the band turns all
the way round about every twenty seconds while its middle loops round the
screen, so the warm and cool colours travel round it, and a wave runs along
its ridge - quicker still while Apollo works. The colours themselves stay
exactly as they are (the idle screen's dusk keeps its slow pace). Over it: the clock with the date in both
calendars, Riyadh's weather, the next prayer and who on your list reports
this week; your watchlist, and under it the status line - the links to
Gemini, Claude and the mic, the market's hours, the machine as rows of lit
segments (CPU, GPU and RAM, sixteen segments each, the last ones warm and
then red), the day's tokens, cost and clips, and the card with each model's
share of the day - two slim lines while LYLA's room is up, the full meters
when it is away; LYLA's health bar at the top right, the way a game shows it
- her portrait, her HP in segments and what she is doing - with **AGENT** on
it (or a click anywhere on the bar) dropping down LYLA's agent card over the
feed: a preview, before she is a real agent, of the pipeline she will run -
your query coming in, a semantic search, LYLA processing, and an email
draft, a CRM update and a report going out - with dots running along the
wires, a line of what she is doing that changes every few seconds and the
workflows ticking up (`ui/full/lylaagent.js`; nothing on it is live yet,
and it says PREVIEW; a click or Escape shuts it); under it
headlines on what you follow and Trump's posts with the market-moving ones
flagged - each topic in its own colour down the story's edge, on its tag
and on its chip (gaming purple, movies red, markets green, Marvel orange,
posts blue, Private Eye cyan). The newest leads, its picture across the
panel drifting slowly, with two lines of what it says; the rest are a line
each like the stocks, with their picture - Bing's, or the one the article's
own page names (`feeds.fill_pictures`), or else the topic's mark. A reading
head moves down them every seven seconds with a line in the story's colour
running under it; a story that has just come in slides into place, and one
under half an hour old says NEW. Over them, a line saying how many stories
there are, from how many sources, and how new the newest is
(`ui/full/feed.js`), and
LYLA in her room along the bottom. The lists - the stocks, the indices, the
feed and its chips, the side panel's tabs - are drawn the way a CRT tool
would: each letter glowing, its red and blue landing a hair either side of
it, and the whole list seen through a halftone of dots.

**The modes.** Along the bottom edge, every mode, the one that is on lit
(`ui/full/modes.js`): **Normal**, the display as it always is; **Clear**,
nothing on the screen but Apollo, bigger, in the middle of it, and under
him a sign - *Press Ctrl + Alt to command Apollo* - with his answer still
shown while he gives it and the bar faint until you point at it (Escape
leaves it); **Trading**, the trading desk (below); **Agents**, the agents
as their pipelines - LYLA, for now (below); **Expanded**, every display at
once (ultra mode, below); and **OSIRIS**, the map laid into the display
(below). Click one, or ask -
*"clear mode"*, *"الوضع الصافي"*, *"الوضع الموسع"*, *"رجع الوضع العادي"* -
and the display comes up if it has to and switches, leaving one mode before
arriving in the next. Beside them, Apollo's own: **Idle** puts him into idle
mode now (the idle screen), **Away** is *"I'm going out"* (the PC kept up
with Claude open until you are back at it) and **Hands-free** is always
listening, what `Ctrl+1` does - the last two lit while they are on. A click
on Idle or Away gives your hand a few seconds to leave the mouse before a
touch counts as you being back (`CLICK_GRACE`). In ultra mode's bar they are
there too, as icons. And **LYLA** puts her room away - she stops,
the room fades, and the panels and the ring grow into the space - and brings
it back; the choice is kept, and *"hide Lyla"* does the same.

**Sounds.** The display makes its own, on the spot, with Web Audio - a few
oscillators and a little noise, swept and shaped like an old synth's blips,
no sound files (`ui/full/sfx.js`). A tick as the pointer comes onto a
button and a click as it is pressed; a glassy step for tabs and chips; two
notes down as a list folds and up as it opens; a filter opening as
something comes up (the display, LYLA's room, her agent card) and closing
as it goes; a sonar ping for OSIRIS and a rush of air for ultra mode.
Apollo starts listening with a rising pair, your words heard with a soft
chime and the answer coming with a bright flick - none on thinking, which
begins before there is anything to have heard. The intro has a slow swell,
sleep and waking their own sweeps, and LYLA her two from the old page.
They are short and quiet, under Apollo's voice, and always on.

The panel on the left has four tabs. **Markets** is the stocks. **Talks**
is what you said to Apollo and what came back, newest first, from the record.
**Projects** is the Claude Code sessions you have been working in (by their
titles), the git folders on your Desktop and in Documents (branch and last
commit - click one to open it in VS Code), and your GitHub repos (click to
open; private ones show only with a token saved as `GITHUB_TOKEN`).
**Ideas** is what you told Apollo to keep - *"فكرة: a Discord bot for the
clan"* - beside your reminders; *"what ideas do I have?"* reads them back.
*"Show my projects"* switches the tab by voice.

Click anywhere on the display and LYLA flies after the pointer for ten
seconds, a little behind it and watching it, then goes back to her day.

The feed is a list you can pick from. Point at a story and a bar slides under
it and its picture opens beside the panel; click it and the story opens out
of its row - picture, summary, and a **Read** button that opens the article in
your browser. Or say it: *"open story three"* opens it (bringing the display
up if it was not) and Apollo tells you what it is. The chips along the top
filter by topic. **FOLD**, at the feed's top right, folds it to the newest
three stories, a line each, with how many are folded under them; **ALL**, or
that row, brings the rest back, and so does opening a story. Kept with the
layout, like the stocks'.

The stocks work the same way - a list after the same component: each row
is the mark and ticker with the name under it, the day's curve drawn small
with where the price sits in the day's range under it, the P/E and the
analysts' target, and the price with the move, in a small spaced-out
monospace. **FOLD**, at the end of the tabs, folds the list away to the first
four stocks, small - the ticker, the curve and the move - with how many are
folded under them; **ALL**, or clicking that row, brings every one back. The
choice is kept with the layout, so it is the same tomorrow. Point at one and the bar slides to
it and the stock's chart opens beside the panel, following the pointer - the
price large, the day's curve, the target, the P/E and anything it earned this
week; click it and the stock opens out of its row: its chart over a day, five
days, a month, six months or a year (run the pointer along it for the close
at any point), the day's range, the analysts' target and the P/E, and
**Remove from watchlist** - which asks for a second click before it does.
When a stock next reports its earnings is in the opened view ("Next
earnings: Tue 17 Nov, in 53 days", marked *est.* while the company has not
fixed the day), on its chart and a lit point by its ticker once it is within
a week, in the morning recap
that week, and by voice (*"when are Nvidia's earnings?"*) - from the same
Yahoo lookup as the target price.
What the people running each company did with its shares is in the
opened view too: open-market buys and sells by directors and officers over
the last 90 days, from their SEC Form 4 filings as Finnhub carries them
(the same key as live prices; tax withholding, option exercises, gifts and
grants are routine and left out). A stock says *Insider buying* when one of
them bought in the last month, the morning recap mentions any trade over
$1M filed in the last two days, and *"are Nvidia's insiders selling?"*
asks by voice. US stocks only.
The row after the last, **Add a stock**, opens a list of suggestions
to put on with a click. By voice: *"open Nvidia"*, *"add Palantir and AMD"*,
*"take off Apple and Tesla"* - in English or Arabic.

Nothing on it is invented. Every number comes from `dataservice.DataService`
through `window.apollo.data(snapshot)`, and the service stamps each reader
separately: when one fails, its panel keeps the last good value and wears its
age in the heading rather than going blank and implying the world went quiet.

It opens on demand, with `` Ctrl+` ``, and stays open until you press the
chord again — typing and moving the mouse in between do not close it.

**Asleep.** After **10 minutes** with no key, no mouse and no voice, Apollo
falls asleep: the screen becomes the idle screen - just *Apollo*, the time,
a fact or two picked at random from what the display already knows (the next
prayer, the weather, a mover on your watchlist, a headline), and *Press any
key or say anything to wake Apollo*, on the same dots turned to dusk. It
falls asleep over the desktop or over the full display, and wakes back to
whichever it was. Any key or mouse movement wakes it, and so does speaking:
while asleep Apollo reads the loudness of the microphone the voice session
already holds - the level only, nothing is recorded or sent - and a sentence
wakes it where a click or a cough does not. It will not fall asleep over a
full-screen program, so a film or a game is left alone.

**Away mode.** Tell Apollo you are going out (*"أنا طالع"*, *"I'm heading
out"*) and the PC stays up with the Claude app open, so you can reach it
from your phone; touch the PC or talk to Apollo when you are back and it
may rest again as the power plan says. Only sleep is held off - the screen
can still turn off.

It also goes idle when you ask - *"ادخل وضع الخمول"*, *"idle mode"* - once
it has finished saying it will, and when you lock the PC (Win+L). Either
way, only something you do after asking wakes it.

A conversation can happen while it is open, and it stays open for it: LYLA and
the panels step aside while there is an answer on screen, then come back.

**OSIRIS.** **OSIRIS** on the bar along the bottom, or *"open OSIRIS"* / *"افتح اوزيرس"*,
lays [OSIRIS](https://osirisai.live) - the open-source intelligence map:
flights and ships, naval and air traffic, CCTV, live news, earthquakes,
incidents around the world, undersea cables, day and night - into the display
where the ring and the feed were, and dresses the whole of Apollo the way
OSIRIS is while it is up: its void, its gold and cyan, sharp corners, a
monospace for everything, the pixels behind in its colours, switched over
like a channel changing. **Close** (or *"close OSIRIS"*) puts Apollo back.

The map is a window of its own laid exactly over the frame (`osiris.py`),
because the site will not be drawn inside another page (`X-Frame-Options:
SAMEORIGIN`) and that is its choice to make. The window has no bridge into
Apollo - nothing on the page can ask Apollo for anything - it browses
privately like every Apollo window, and it goes whenever the display goes.
Before it went in, the site was read through: everything comes from
osirisai.live itself behind Cloudflare, with no ads, no third-party trackers,
no miner and nothing that touches a wallet. It does carry tools that look at
the machine they run on - a scan of your own PC's local ports and addresses,
a Bluetooth scanner, live location - and each runs only when you open that
tool; Bluetooth and location still ask first.

**The scanner.** At the foot of the feed's column, folded away until a file
is being scanned - the console's SCAN is how to start one. **Choose file** opens File Explorer over
the display - which fills the screen, so there is nothing behind it to
drag from - and what you pick is read and judged, never run or opened:
clean, careful or dangerous, with why (`scanner.py`). A file dropped on the
display is scanned the same way, and so is asking: *"scan a file"* / *"افحص
ملف"* opens File Explorer (the `scan_file` tool). The SCAN button on the
console does it too.

**The HUD.** The normal display is yours to arrange. **F2**, HUD on the
console, or *"customize the HUD"* / *"عدل الواجهة"* opens the editor: every
panel - the clock, the stocks, the system, Apollo, LYLA, the feed, the
scanner and the two consoles - in a frame. Drag one and it follows your hand
on a spring, leaning into the way it moves, and lands on the grid or lines
up with the edge or middle of another panel (a cyan guide shows which); a
corner resizes it, and Apollo and the consoles grow as a whole; the wheel
or **+ / −** makes what is inside larger or smaller (double-click for 100%);
the eye hides it; the arrow keys nudge the one you last touched. **Snap**
turns the pulling off, **Reset all** flies every panel home, and **Done**,
Enter or Escape closes it. It is kept (`hud.py`,
`%LOCALAPPDATA%\Apollo\hud.json`) and laid out whenever the normal display
is up; every other view and ultra mode lay themselves out as ever.

**Trading mode.** **Trading** on the bar, or *"trading mode"* / *"وضع
التداول"*, turns the display into a trading desk of six displays
(`trading.py` reads them, every ten minutes while the desk is up and not at
all otherwise). It has a style of its own rather than Apollo's: the market's
greens on ink - the ground behind it goes over to them too, and the bar and
the clock take them while it is up - teal for the labels, gold for a
warning, red for what falls; set in Thmanyah like the rest of Apollo, with
the tickers and figures in Martian Mono (bundled, SIL Open Font License).

- **The read** - the next picks, where the signals agree: each ticker scored
  by how many kinds of signal point at it (trending with traders, bullish
  messages, Reddit mentions rising, insiders buying, Congress buying, the
  traders you follow on X) and how strongly, with its reasons and the
  crowd's own summary of why it is talking about it. Agreement ranks first:
  two kinds of signal beat one strong one.
- **Traders** - what is trending on StockTwits, with how bullish its tagged
  messages are, and the most mentioned stocks on Reddit's finance
  communities (ApeWisdom), with how fast the mentions are rising.
- **Sensitive** - the SEC's feed of 8-K current reports ranked by how
  serious the event is (bankruptcy, restatement, delisting notice, change
  of control, deals signed or ended, executives leaving...), and
  market-moving headlines (Finnhub's market news and a search for halts,
  FDA decisions, deals, probes, guidance cuts, downgrades). The SEC answers
  only requests that name a contact, and Apollo gives it yours (`SEC_CONTACT`
  in `trading.py`; the `SEC_CONTACT` variable overrides it, `off` stops it).
- **Insiders** - OpenInsider's screens of Form 4 filings: cluster buys
  (several insiders of one company buying at once, the strongest insider
  signal) and the biggest open-market purchases.
- **Congress** - House and Senate trades disclosed under the STOCK Act.
- **On X** - the traders you follow, if you give Apollo an X API bearer
  token (`X_BEARER_TOKEN`) and their accounts (`X_TRADERS`, comma-separated).
  X has no free tier: reads cost about half a cent a post, so Apollo reads
  at most `X_DAILY_READS` a day (100 unless you say). Until then the panel
  shows where your own stocks turn up on the desk.

Click a filing, a headline or a disclosure to open it. By voice, *"what are
traders buying?"* / *"وش السهم الجاي"* gives the read in a few sentences
(the `trading_read` tool). It is a read of the crowd and the filings, not
advice, and the desk says so.

**LYLA does the research; Apollo stays yours.** Ask Apollo for something
that takes looking into - *"حلل لي سهم انفيديا"*, *"analyse AMD for me"*,
*"research the best budget GPUs"* - and he hands it to LYLA (`lyla.py`, the
`ask_lyla` tool) and is free again at once: give him the next thing while
she works. She works on a thread of her own, one job at a time. For a stock
she reads the price and its month, the valuation and the analysts' target,
where it turns up on the trading desk, what traders are saying about it on
StockTwits, its insiders' trades and the week's news, then writes it up -
what the company does, the price, the signals, the catalysts, the risks and
a lean, a read and not advice - searching the web for the rest. When she is
done Apollo tells you in two or three sentences, in his voice and your
language, after any turn in progress (the way a reminder waits); *"what did
LYLA find?"* reads her report back (`lyla_findings`). While she works her
line under her HP bar says ON A JOB, and her reports are listed in agents
mode, newest first - click one for the whole thing. They are kept between
sessions (`%LOCALAPPDATA%\Apollo\lyla_reports.json`, the last twenty).

She works for Apollo; she does not drive him. She has no tools that touch
your PC or the display and never takes the screen - she reads and she
writes. What she thinks with, the first that answers:

- **Hermes** ([hermes-agent](https://github.com/NousResearch/hermes-agent),
  Nous Research's open-source agent - free, MIT), if you run its API server
  and tell Apollo where it is: `HERMES_URL` (`http://127.0.0.1:8642`) and
  `HERMES_KEY` (the `API_SERVER_KEY` in `~/.hermes/.env`). Hermes costs
  nothing itself; the model it runs on is the cost, and it can run on Gemini
  with the key you already have.
- **Gemini** otherwise, with Google Search, on `GEMINI_API_KEY` - nothing to
  set up. `LYLA_MODEL` puts a model of your choice first.

**Agents mode.** **Agents** on the bar, or *"agents mode"*: the agents by
their marks down the left, each in its own colour and shape - LYLA's lens
(blue, research), and as previews of the agents to come, ATLAS's compass
(orange, a planner), NOVA's burst (magenta, a creator) and ECHO's waves
(teal, memory). Click a mark and that agent's process opens beside it -
its pipeline card, in its colours, with LYLA's reports under hers; click it
again to put it away. Her mark says READY, LIVE or ON A JOB; the other
three say PREVIEW, run a demo of what they will do, and never go live.
Until LYLA first works her card is a preview on a loop too and says PREVIEW. Hand her a job
through Apollo, or say *"hey LYLA, ..."*, and her card goes LIVE: the job,
each thing she reads, her writing it up, then the answer with how long it
took and what she thought with (or the error), her runs counted and her
latency averaged. The card on her HP block runs live the same way. Neither
changes what the display is showing: go to agents mode to watch her.

**Ultra mode.** **Expanded** on the bar along the bottom, or *"ultra mode"* /
*"وضع الشغل"* / *"جهز الشاشة للشغل"*, gets Apollo ready for work: a channel
change, a line of light down the glass, and every display powers on one
after another as a tile on a grid of twelve columns and twelve rows - the
OSIRIS map in the middle, the markets and the feed either side, and along
the bottom your projects, your ideas, Apollo himself and the system; your
talks are one switch away. It gives more than the normal display does:
**Today** adds the next prayer, the market's hours, who on your list reports
or has an insider buying this week, and what is due; **System** adds what
Gemini and Claude each took today, the turns and the cost, the graphics
card, the clips, and how fresh every reading is.

Every display is yours to arrange. Drag one by its top edge onto another and
the two trade places; drag its bottom corner and it grows or shrinks a cell
at a time. In its top corner: **minimize** (it folds to its name and the
one line that matters - the indices and the biggest mover, the next prayer,
CPU and tokens), **expand** (it takes the screen and the rest line up
minimized down the side - click one to swap), **settings** (its size by
name or a column and a row at a time, the feed's topic, the map's layers)
and **hide**. The bar along the bottom has the modes, switches each display
on and off, puts the grid back, and resets the lot. Either side of it sits
a facility's desk, for the look of the place: switches that flip with their
lights, a strip of status lights, armed buttons that fire (SCAN, HUD, LOCK,
PURGE), a dial that turns a quarter at a time, and readouts. The readouts
and the lights are real (`ui/full/consolelights.js`): how long Apollo has
been up, how quickly the internet answers (`LINK`, from `sysinfo.link_ms`,
red when it does not), the CPU with its last six readings as bars, the
card's heat; and eighteen lights - the six sources green while fresh and
amber once old, then listening, thinking, speaking, hands-free, away and
LYLA on a job, then the CPU as a meter - each saying what it is under the
pointer. Two of the buttons do something: SCAN opens File Explorer to
choose a file for the scanner, HUD opens the HUD editor (below); the rest
click and light. On a screen narrower than 1900 pixels they step away to
leave the bar its room. In the normal display they sit at the foot of the
feed's column, side by side, step aside while a scan report is open, and
fade away with everything else on the idle screen. By voice: *"put the projects on my
screen"* / *"حط المشاريع على الشاشة"* pulls that display up, expanded, with
the rest minimized - bringing the display up first if it has to; *"all of
them"* puts the grid back; *"hide the ideas"* and *"show my talks"* work on
ultra mode's displays while it is up. Expanded, OSIRIS dresses Apollo in its
colours as it does on the normal display. How you left it - what is shown,
where, how big, the map's layers - is kept (`displays.py`), so the screen
you set up is the one you get tomorrow.

The map's window can only lie over the page, never under it, so in ultra
mode it steps aside - parked, still loaded - while a display is being moved
or set up, while it is minimized or another one is expanded, and while
Apollo answers, and comes back over its frame once things settle.

### Hotkeys

| Chord | Does |
|---|---|
| `Ctrl+Alt` (hold) | Talk. Hold, speak, release. |
| `Ctrl+1` (press) | Toggle always-listening — talk without holding anything. |
| `` Ctrl+` `` | Open or close the full display. |
| `Ctrl+Alt+Shift+Q` | Quit Apollo. |

> **How the chords are tested, and why it matters.** `keyboard.is_pressed`
> only tests that the named keys are *down*; it never checks that others are
> up. With `Ctrl+Alt` as the talk chord that would mean every chord containing
> it — `Ctrl+Alt+Shift+Q`, and every `Ctrl+Alt+<letter>` belonging to whatever
> app you are using — started a recording. So the talk chord is tested
> **exclusively** by `assistant.talk_held`: both halves down, and nothing else
> down at all. Pressing `Ctrl+Alt+<key>` still opens a recording for the few
> milliseconds before the third key lands, but that clip is far under
> `MIN_SECONDS` and is discarded.
>
> The global chords do not use the `keyboard` library at all. Measured here:
> `keyboard.is_pressed("ctrl+`")` returns `False` for the entire time both
> keys are genuinely held — it resolves the backtick to scan code 41 and its
> hook never matches — so the chord silently never fired. `apollo.chord_down`
> reads `GetAsyncKeyState` directly instead, which reported both keys
> correctly at the same instant.
>
> `` Ctrl+` `` was chosen for expand because it shares no key with the talk
> chord, so opening the display never records a fragment of a turn.
>
> On a non-US layout where **AltGr** types characters, AltGr *is* `Ctrl+Alt` —
> so on those layouts the talk chord will fire while you type. Change `HOTKEY`
> and `talk_held` in `assistant.py` if that is you.
>
> `Ctrl+1` is the number row's 1, not the numpad's, so typing figures never
> trips it. It is a press rather than a hold, and it is read by the same
> `GetAsyncKeyState` polling as the others (`assistant.ListenToggle`) for the
> same reason: `keyboard.add_hotkey` callbacks do not fire on this machine.

### Always-listening

Press `Ctrl+1` and Apollo stops waiting for the chord: the microphone streams
continuously and **Gemini decides where your sentences end**, so you just
talk. Press it again and everything goes back to `Ctrl+Alt` hold-to-talk.
Push-to-talk is always what Apollo launches in — always-listening is something
you turn on, never something you arrive to.

The two modes are genuinely different sessions, not a flag, and the reason is
worth knowing before you change anything here. Who detects the end of your
sentence is fixed when the session connects:

- **Push-to-talk** must *not* use the model's voice activity detection.
  Releasing the chord cuts the audio off mid-word with no trailing silence to
  score, so the detector never fires and the turn hangs with **no reply and no
  error**. The chord is unambiguous, so Apollo sends `activity_start` /
  `activity_end` instead.
- **Always-listening** must use it. Nothing cuts the stream, so there is
  always silence to hear — and there is no key to take the cue from anyway.

So toggling reconnects, which takes about a second. That is also what
guarantees there is never more than one microphone path open: there is one
session, and it is in one mode.

While always-listening is on the orb holds its *listening* state rather than
blooming for one turn, which is the cue that the microphone is not waiting on
a key.

### Stopping it

Right-click the **Apollo** tray icon and choose *Quit Apollo*, or press
`Ctrl+Alt+Shift+Q`. `ESC` deliberately does **not** quit: Apollo runs for days
behind whatever you are using, and a global `ESC` would mean that dismissing
any unrelated dialog silently killed your assistant.

Running `start.bat` twice is harmless — Apollo holds a single-instance lock, so
the second copy sees the first and exits rather than grabbing the microphone a
second time.

**Console version.** The overlay is optional — `assistant.py` still runs on its
own with the same behaviour, printing instead of drawing (and there `ESC` does
quit, because it is the foreground app):

```powershell
.\.venv\Scripts\python.exe assistant.py
```

---

## Stocks

Ask about a stock and the overlay becomes that stock's card: the company's
mark, the ticker and name, the price with the day beside it, a smooth curve,
and along the foot what the analysts think it is worth and what it costs per
unit of earnings. The full display carries the same card for every name on
the watchlist.

Three things there come from outside the chart feed:

| | Where from | If it fails |
|---|---|---|
| Target price, P/E | Yahoo's `quoteSummary` (`market.fundamentals`) | the card shows a dash |
| Company marks | a public logo endpoint, cached in `ui/full/logos/` | the card shows the first letter |
| Prices and the curve | the chart endpoint Apollo already used | the answer fails, and says so |

`quoteSummary` has answered 401 to anything without a crumb since 2023, so
`market.fundamentals` takes a cookie from Yahoo, trades it for a crumb, and
sends both; the crumb is kept for an hour. It never raises — a missing
valuation is a gap on the card, not a failed answer.

A valuation lookup inside a turn gets `market.TURN_TIMEOUT` (2.5s) rather
than the usual six, because a stock that is not on the watchlist has nothing
cached and two hosts at six seconds is twelve seconds of silence for a number
the card can live without.

The marks are other companies' trademarks, fetched from a third party. They
are cached at runtime and git-ignored, never committed.

**Live prices.** With a free Finnhub key saved as `FINNHUB_API_KEY`
(`setx FINNHUB_API_KEY "..."` from finnhub.io's dashboard, then restart
Apollo), prices move as they trade. `live.LiveFeed` holds one WebSocket to
Finnhub for the watchlist's US stocks and hands the latest trade per stock
on about once a second: the cards' prices tick and flicker the way they
went, the end of each curve follows, an opened stock's day chart grows at
its edge with a dot pulsing at the price, and the panel says **Live** while
trades are coming. A price asked for out loud takes the stream's price, or
Finnhub's quote for a US stock that is not on the list. The free stream has
no indices, no Tadawul, no futures or crypto; those stay on the minute-by-
minute reading, and so does everything when the market is shut or the
stream is down (it reconnects by itself). The key rides in the stream's
address, so the address is never logged. No key, no stream: nothing else
changes.

Changing the watchlist answers at once. The tools ask the data service to
read the market again (`DataService.poke`) and return; the new card follows
a moment later. They used to read every feed there was before answering,
and Apollo sat silent through all of it. Company names go to the market
search in English - the tool asks the model to translate, and a name it
cannot place comes back saying to try the English name or the ticker, so
the model retries. One call takes several companies, and a change holds a
lock from read to save, so three at once all stick.

## A note on the typeface

Apollo sets both Arabic and English in **Thmanyah Sans**, carried in the
repository rather than expected from Windows: the overlay loads the OTFs into
a private GDI+ collection, and the display loads the WOFF2s with `@font-face`.
One family for both scripts is the whole reason for it. (The full display
sets its English in IBM Plex Mono now; its Arabic still falls through to
Thmanyah.)

**Its licence permits this and forbids publishing it.** Embedding the font in
an application you build is expressly allowed; redistributing the files, or
hosting them anywhere a third party can download them, is not — and that
includes pushing this repository to a public remote with `ui/fonts/` and
`ui/full/fonts/` in it. The repository has no remote today. If one is ever
added, remove those two directories from the history first, or ask thmanyah
(ask@thmanyah.com) for the extended rights. The full licence is at
`ui/fonts/thmanyah/LICENSE.pdf`.

If the files are missing, both halves fall back: the overlay to Segoe UI, the
page to the system sans. `tests/test_fonts.py` and `tests/test_page_assets.py`
fail when a weight goes missing, because that fallback is silent and the
result looks almost right.

## How the window works

Apollo is two always-on-top, non-focusable windows, and only one of them is on
screen at a time: the native overlay (`orb.py`), which is what you see for a
whole conversation, and the page window, which is only ever the full display.
Both are frameless, and the same extended window styles keep them out of your
way:

| Style | Effect |
|---|---|
| `WS_EX_TRANSPARENT` + `WS_EX_LAYERED` | Clicks fall through. Both are needed — `TRANSPARENT` alone does not stop a WebView2 window hit-testing. |
| `WS_EX_TOOLWINDOW` | No taskbar button, no Alt+Tab entry. |
| `WS_EX_NOACTIVATE` | Never takes focus, so your caret stays where it was. |

The full display is translucent via
`SetLayeredWindowAttributes(..., LWA_ALPHA)` — see `ALPHA` in `apollo.py`. The
overlay does not use it: it has real per-pixel alpha instead, which is the
whole reason it exists.

### Why the overlay is not HTML

The overlay is drawn natively, in `orb.py`, and the full display is the HTML
design. That split exists because **a WebView2 window cannot be given
per-pixel transparency here**, which was measured rather than assumed:

| Attempt | Result |
|---|---|
| pywebview `transparent=True` | **broken** — assigns `DefaultBackgroundColor` to pywebview's own `EdgeChrome` wrapper, a plain Python object, so it never reaches WebView2 |
| Setting it on the real control | no help — it already reports alpha 0; the WinForms host behind it is what paints |
| Form `BackColor` | works, and is used — black instead of the default near-white `#F0F0F0` |
| `LWA_ALPHA` | **works** — real, uniform translucency; this is what the full display uses |
| `LWA_COLORKEY` / `TransparencyKey` | ignored — the page reaches the screen through DirectComposition, never through the layered surface a key would act on |
| `DwmExtendFrameIntoClientArea(-1)` | no effect |
| `SetWindowCompositionAttribute` (blur / acrylic) | no effect |
| `WS_EX_NOREDIRECTIONBITMAP` | rejected — creation-only, and pywebview owns window creation |
| `SetWindowRgn` circle | clips, but the backdrop still paints: a grey square survives around the circle |

That last row was the visible bug: a black circle sitting on a grey tile.

It is also why an answer is drawn by `orb.py` rather than by the page. A reply
used to square the overlay off into a 460×300 panel and hand over to the page
to fill it — but that window can only ever be an opaque rectangle here, and a
rectangle arriving on your desktop is exactly what an ambient overlay should
not do. Text, sparkline and cards are all GDI+ on the layered surface now, so
an answer floats on the desktop the same way the mesh does.

So the orb is drawn with GDI+ into a 32-bit ARGB bitmap and handed to a layered
window with `UpdateLayeredWindow` — the one path on Windows that gives true
per-pixel alpha. Round where it is round, invisible everywhere else, soft glow
edges, click-through by construction. The page window is simply hidden while
Apollo is at rest.

**Why not a true wallpaper?** Reparenting into Explorer's `WorkerW` — the
Wallpaper Engine approach — puts Apollo *behind* every window, so you could
talk to it but never see the answer unless your desktop happened to be bare.
It is also fragile: the `WorkerW` handle dies whenever Explorer restarts, and
WebView2 composites unreliably outside the normal window hierarchy.

---

## What it can do

You don't switch modes or say a magic word: whichever model is answering -
Gemini for conversation, Claude when you summon an agent - decides from what
you asked, and both have exactly the same tools (`tools.py` declares them once
for both). Apollo does the thing first and then confirms it in a few words.

| Ask | What happens |
|---|---|
| *"Open Spotify"*, *"close Notepad"* | Launches or switches to the app; closing sends a normal close, so the app still asks about unsaved work. |
| *"Open YouTube"*, *"open github.com"* | Opens the site in your browser. An unknown phrase becomes a Google search. |
| *"Open my Downloads folder"*, *"open the readme"* | Files and folders by path, standard folder name, or a search of your user folders. |
| *"Pause the music"*, *"next song"* | Media keys, so it works with Spotify, YouTube and anything else playing. |
| *"Volume to 30"*, *"turn it down"*, *"what's my volume?"* | Real volume control and read-back. |
| *"Minimize this"*, *"snap Chrome left"*, *"show the desktop"* | Window control; with no app named it acts on the window in front of you. |
| *"Type: see you at nine"*, *"press ctrl+t"* | Types into (or sends a shortcut to) whatever window you're working in - Arabic too. |
| *"Remind me in 20 minutes to stretch"* | Reminders are spoken back in Apollo's voice when due, and wait for you to finish talking first. |
| *"How's Nvidia doing?"*, *"chart Tesla for a month"* | Live prices from Yahoo Finance; a chart and readouts appear under the mesh, and Apollo speaks only the numbers the feed returned. |
| *"Open it in TradingView"* | Opens the full interactive TradingView chart for that symbol. |
| *"Lock the PC"* | Locks at once. **Sleep, restart, shut down and sign out** always ask first, and only a "yes" in your *next* turn goes through - the model cannot approve its own request. Restart and shutdown wait 10 s; *"cancel the shutdown"* stops them. |
| *"Clip that"*, *"save the last minute"* | Writes the last 60 s of screen and system audio to `Videos\Apollo's Clips`. |
| Anything current | Gemini uses Google Search rather than answering from memory. |

**Clips.** Apollo keeps the last 60 seconds of your screen in memory, all the
time it is running, and *"clip that"* (or *"save the last minute"*, or the same
in Arabic) writes it to `Videos\Apollo's Clips` as an MP4 with the system audio
- what the speakers were playing, never your microphone.

Nothing is ever written until you ask: the buffer is RAM only, about 96 MB for
those sixty seconds, and it costs roughly two thirds of one core (6% of this
machine) at 1080p30. The tray menu has a **Pause replay buffer** switch.

> It records with `gdigrab`. The GPU's own capture (`ddagrab`) is faster and
> nearly free, but when it fails to start it hangs inside FFmpeg *holding the
> GIL*, which freezes every thread in Apollo - so it is opt-in only, with
> `APOLLO_CAPTURE=ddagrab`, on a machine where it has been proven.

## What Apollo knows

Apollo keeps a picture of your day up to date in the background, so a question
about it is answered from something read seconds ago rather than from a model's
memory:

| | Source | Refreshed |
|---|---|---|
| Your watchlist and the indices | Yahoo Finance | every minute while New York trades, else every 15 |
| Headlines on gaming, Marvel, movies and markets, with pictures and summaries | Bing News RSS, Google News when Bing has nothing | every 10 minutes |
| Trump's posts, market-moving ones flagged | trumpstruth.org | every 5 minutes |
| Riyadh's weather | Open-Meteo | every 15 minutes |
| CPU, memory and the GPU | the machine itself | every 5 seconds |

None of them needs a key or an account, and none of them can break a
conversation: a feed that is down gives its last answer with an honest age on
it, or nothing at all.

**The daily recap.** Say *"brief me"* or *"what did I miss"* and Apollo reads
you the day: the date (Gregorian and Hijri), the weather, where the market
stands and what your stocks did, the two or three stories that matter to
you, anything market-moving Trump posted, and your reminders. About 40
seconds, in whatever language you last used, and `Ctrl+Alt` cuts it off
like any other answer. It no longer plays by itself when Apollo starts
(`DAILY_RECAP` in `apollo.py`).

**What it remembers about you.** Apollo keeps a record of your days on this
PC and nowhere else (`journal.py`, `%LOCALAPPDATA%\Apollo\journal`): what
you said, what he answered, the tools he used, and the stories and stocks you
opened. The last 60 days are kept. The first time Apollo is running after a
day ends, one question to Claude reads that day with what he already knows and
updates a small profile (`interests.py`, `%LOCALAPPDATA%\Apollo\profile.json`):
what you care about and how much, what you do not, and a few lasting facts.
Gemini reads a summary of it at the start of every session, so Apollo knows
you without being told. Interests that stop coming up fade. Nothing is
trained: the models are the same; what changes is what they are told. Delete
the journal folder and `profile.json` to make him forget.

**Private Eye.** Apollo's scout (`private_eye.py`). Every three hours it
searches free sources - Bing News, Hacker News and Reddit - for your strongest
interests and keeps the five best finds you have not been shown: about what
you care about most, fresh, and never about something you said you do not
care for. They sit in the feed marked *Private Eye* (and alone under their own
chip), go into the morning recap, and Apollo tells you about them when you ask
*"what did Private Eye find?"*. Open one and press **Useful** or **Not for
me**, or say *"number two is مهم"* / *"مو مهم"*: its interest moves up or down,
and that is what the next search goes by. It costs nothing but the few cents
of Claude's nightly pass.

**What it costs.** Neither provider tells an ordinary API key what it has
spent, so Apollo counts its own tokens as they are reported and keeps a daily
ledger in `%LOCALAPPDATA%\Apollo\usage.json`. The figures on screen are
**estimates** from the price table in `usage.py` — edit it to match your bill.

---

**Language.** Apollo answers in the language you spoke - Arabic (in a Saudi
dialect) or English - because what you say is transcribed by Gemini itself,
which understands both. The live words under the mesh stream as you talk.

**Research properly.** Summon an agent (*"Hey ATLAS, research ..."*) and Claude
runs a much heavier pass: around a dozen searches, fetching the important
sources in full, cross-referencing numeric claims. It takes a minute or two and
**costs meaningfully more than a normal question** - see [Cost](#cost).

**The voice model.** Apollo connects to the first model in
`gemini_live.MODELS` that answers - `gemini-2.5-flash-native-audio-latest`,
then the September 2025 preview - and says which in the log. Set
`APOLLO_GEMINI_MODEL` to try another first. `gemini-3.8-live` exists but needs
billing enabled on the Gemini key (it currently reports "exceeded your current
quota").

---

## What's already been done for you

- Virtual environment created at `.venv` with all dependencies installed
- Verified your mic works (`Microphone (picun G2)`) and two TTS voices exist
- Whisper `small` (multilingual) downloads in the background on first run; it is only a backup
- VoiceBox running on `127.0.0.1:17493` with the `Apollo George` voice profile,
  and Piper `en_US-lessac-medium` in `voices/` as the fallback

The only thing left is your API key.

---

## Files

| File | What it is |
|---|---|
| `assistant.py` | The engine: hotkey, mic, Whisper, routing, Claude, tools, TTS. Runs standalone in the console. |
| `gemini_live.py` | Apollo's voice. Owns the only microphone Apollo opens and streams it to Gemini's native-audio model, which answers in the Puck voice as audio rather than as text to be synthesised. Holds both listening modes. |
| `router.py` | Which backend answers this turn. One question: was an agent called by name? Everything else is conversation. |
| `agents.py` | The seven agents, and the only module that touches `ask_claude`. Placeholders for now — the boundary exists before they do, on purpose. |
| `tools.py` | Every tool Apollo has, declared once for both Gemini and Claude, and the only place tool errors are caught. Also the confirmation rule for power actions. |
| `pc_control.py` | The Windows side of the tools: apps, sites, files, keyboard, media, volume, windows, power. Talks to Windows, never to a model. |
| `market.py` | Live prices, history, NYSE hours and TradingView links, from Yahoo Finance's public feed. |
| `feeds.py` | Headlines and posts, from keyless RSS feeds, cached and total. |
| `weather.py` | Riyadh's weather from Open-Meteo. |
| `sysinfo.py` | CPU, memory and the NVIDIA card, through NVML. |
| `usage.py` | The day's token ledger and an estimated cost. |
| `briefing.py` | What the recap contains, and whether today's has happened. |
| `dataservice.py` | The one background thread that keeps all of it fresh. |
| `clips.py` | The replay buffer: the last minute of the screen and system audio, in memory, and the MP4 a save writes. |
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
| `ui/full/lylaagent.js` | The agents' pipeline card - LYLA's live, ATLAS's, NOVA's and ECHO's as previews, each in its own look - and each agent's mark: the pipeline, its moving parts and what opens and shuts it, ported from a React component to plain JS and SVG, so there is still no build step (`tests/test_lyla_agent.py`, `tests/test_agents_rail.py`). |
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
| `start.bat` | Double-click launcher. Runs `pythonw.exe`, so there is no console window. |
| `install-startup.bat` | Adds Apollo to Windows startup. `uninstall-startup.bat` removes it. |
| `voices/` | The downloaded Piper *fallback* voice (~63MB). Only used when VoiceBox is down. Delete it and it re-downloads. |
| `.venv/` | The virtual environment |

### One voice, and the door Claude is behind

**Everything you say to Apollo is answered by Gemini Live in Puck's voice.**
Chat, a quick command, a question about your own code, a hard one — all of it,
in both listening modes. Your voice is already streaming to Gemini while you
are still speaking, and the reply comes back as audio. Nothing is synthesised:
the model *is* the voice, which is why it is fast.

This used to be a keyword match — words like *refactor* or *architecture* sent
a turn to Claude instead. It worked, and it was the wrong idea, for a reason
that has nothing to do with how good the word list was. The two backends speak
in **different voices** (Puck for Gemini, Fish or VoiceBox for Claude), so the
rule was not choosing a model, it was choosing which of two people answered
you, based on whether your sentence happened to contain a technical word. Ask
about your weekend, get one voice; ask about your code, get another. No amount
of tuning fixes that, so it is gone.

Claude has not gone anywhere — it still has the tools (web search,
`control_pc`, deep research). It is reached by **summoning an agent by name**:

    LYLA · ATLAS · ECHO · NOVA · THE WORKSHOP · OPTIMO · HERMES

Say *"Hey LYLA, …"* or *"ask ATLAS to …"* and that turn goes to the agent,
which answers in the Fish/VoiceBox voice. Anything else is conversation. Four
of those names are ordinary English words, so a name only counts as a summons
when it is used to *address* someone — at the start of what you said, or after
a word like *hey*, *ok* or *ask*. "The echo in this room is terrible" is
conversation; "Echo, play that back" is not.

None of the seven are built yet. `agents.py` is the boundary they will be
built behind, and for now `agents.handle` passes the request to Claude and
says which agent was asked for. The rule that matters, and the one to keep
when they land: **`ask_claude` is called from `agents.py` and nowhere else.**

Every turn logs where it went and why:

```
  [apollo.router] -> GEMINI LIVE  "refactor this class"          (conversation)
  [apollo.router] -> AGENT LYLA   "hey LYLA take a look at this" (LYLA summoned by name)
```

In always-listening, a summons has to interrupt: Gemini starts answering
before you have finished the sentence, so `agents.detect` runs on the words as
they arrive and stands it down mid-reply.

Gemini Live owns the microphone for the whole session rather than opening one
per turn, and Whisper reads along from the same blocks (`assistant.LiveCapture`)
— one device, two readers. Without a `GEMINI_API_KEY` Apollo has no voice and
says so; it does not quietly answer in Claude's instead, because that
substitution is the thing this design removes.

The split is deliberate: `assistant.py` reports what it's doing to a small
"reporter" object (`status` / `turn` / `note` / `fatal`) instead of printing.
The console uses `ConsolePrinter`; the overlay uses `WebReporter`, which
marshals every call into the page as a one-line `window.apollo.*()` call.
Anything slow — the mic, Whisper, the API call, TTS — runs on a worker thread,
and that thread only starts once the page has loaded, so there is always
something on the other end to report to.

### Changing the display

Edit `ui/full/` directly — plain ES modules, no build step. To look at it
without running Apollo, serve `ui/` and open `full/index.html`; a sample
snapshot is baked into `app.js` so every panel has something in it. To check
it in the window Apollo actually uses:

```powershell
.\.venv\Scripts\python.exe probes\probe_full_display.py
```

`probes\probe_feed_shots.py` screenshots the feed, a story opened out of it
and the idle screen, with the real feeds in it. `probes\probe_stock_shots.py`
does the same for the stocks - a card picked, one opened over each span, one
removed and one added - on a watchlist of its own. Both take the screen for a
minute and capture whatever is on top of it, so leave the machine alone
while they run.

One trap worth knowing: pywebview roots its HTTP server at the page's own
directory, so anything the page references has to live under `ui/full/` —
`../anything` resolves in a browser and 404s in the window, silently.
`tests/test_page_assets.py` fails on any reference that climbs out.

`ui/legacy/index.html` is the design this replaced, kept because LYLA was
lifted out of it. `build_ui.py` still regenerates it from the `.dc.html`
export, and nothing in the run reads either one.

Tools follow the same principle. `assistant.py` owns the conversation with
Claude and decides nothing about Windows; `pc_control.py` owns Windows and
knows nothing about Claude. Between them sits one small dispatcher
(`_run_tool`) that turns a tool call into a string to hand back. Adding a
capability means writing a schema in `TOOLS` and a handler — nothing else in
the loop changes. Web search is the exception that proves it: it runs on
Anthropic's servers, so there's no handler at all, just a declaration.

---

## Tweaking it

All the knobs are at the top of `assistant.py`:

| Setting | Default | Notes |
|---|---|---|
| `HOTKEY` | `ctrl+alt` | Held to talk. Tested exclusively by `assistant.talk_held`, so chords that merely *contain* it (`ctrl+alt+shift+q`) do not fire it. |
| `WHISPER_SIZE` | `base.en` | `tiny.en` is faster, `small.en` is more accurate. Downloads on first use. |
| `FISH_VOICE` | `a4c68282...` | The spoken voice: a Fish Audio voice model id. Defaults to a bright, energetic British female voice. See below. |
| `FISH_BACKEND` | `s1` | Fish's synthesis model. `speech-1.6` is cheaper and a little rougher. |
| `VOICEBOX_PROFILE` | `Apollo Emma` | The **offline** voice, used when Fish is unreachable or out of credit. Matched by name against VoiceBox's `GET /profiles`. |
| `VOICEBOX_URL` | `http://127.0.0.1:17493` | Where VoiceBox listens. Loopback only; nothing leaves the machine. |
| `VOICEBOX_ENGINE` | `kokoro` | VoiceBox's synthesis engine. `kokoro` is the CPU-friendly one, and the only one with British presets. |
| `PIPER_VOICE` | `en_GB-jenny_dioco-medium` | The fallback voice, used only when VoiceBox is unreachable. British female. Downloads on first use. |
| `VOICE_RATE` | `185` | Words per minute — **Piper and SAPI only**. `POST /generate` has no speed parameter, so it does not affect VoiceBox. |
| `CLAUDE_MODEL` | `claude-opus-5` | `claude-sonnet-5` is ~2.5x cheaper and still very good for chat. |
| `SYSTEM_PROMPT` | ~40 words, optimistic + firm | Sets Apollo's character (optimistic, game for a challenge, firm) with explicit guards against that becoming cheerfulness, bluster, curtness, or longer answers; caps replies at three sentences and about forty words with no paragraph breaks; tells Apollo what it is, so it stops asking which app its own voice belongs to; and tells Claude when to reach for a tool. Measured effect: mean reply 53 → 42 words. |
| `RESEARCH_SEARCHES` | `12` | How many searches a deep-research pass may run. The main cost lever — see below. |

And the overlay's own knobs, at the top of `apollo.py`:

| Setting | Default | Notes |
|---|---|---|
| `AFK_SECONDS` | `600` (10 min) | How long the machine must go untouched - no key, no mouse, no voice - before Apollo falls asleep on the idle screen. |
| `PEEK_HOTKEY` | `ctrl+`` ` | Opens/closes the full display. Shares no key with the talk chord, so expanding never records a fragment of a turn. |
| `ORB_PX` | `190` | The mesh's own box. The overlay grows downward from the top of it; the mesh itself always sits in a square of exactly this size. |
| `ORB_REVEAL` | `0.25` | How much of the mesh stays below the top edge; the rest hangs off-screen. |
| `ALPHA` | `orb 225, full 250` | Window translucency, 0–255, for the page window. The overlay itself has real per-pixel alpha and does not use it. |
| `LINGER` | `4.0` | Seconds an answer stays up after Apollo stops speaking, before it collapses. |
| `QUIT_HOTKEY` | `ctrl+alt+shift+q` | |

**Changing the voice.** Set `VOICEBOX_PROFILE` to the *name* of any profile in
VoiceBox — it is resolved to an id against `GET /profiles` at startup, so
rebuilding a profile doesn't break the setting. Apollo is female on every rung
of the chain; these five female Kokoro presets exist as profiles already:

| Profile | Kokoro voice | Sounds like |
|---|---|---|
| `Apollo Emma` | `bf_emma` | Warm RP, British. **The default.** |
| `Apollo Isabella` | `bf_isabella` | British too, poised and a little cooler |
| `Apollo Bella` | `af_bella` | American, the brightest and most expressive |
| `Apollo Nova` | `af_nova` | American, crisp and clipped |
| `Apollo Heart` | `af_heart` | American, warm and steady |

Auditions are in `voicebox_samples/` — `f1`–`f5` are the female five in the
order above (`f4` is the default), and `1`–`4` are the older British male
profiles, which still exist if you want to go back. The female profiles use a
lighter effects chain than the male ones: a 120 Hz high-pass, a gentle
compressor and +4 dB, with no 3.5 kHz low-pass — that band-pass is what made
the male voices sound like a radio, and it strips exactly the brightness an
optimistic voice lives on. To add more, make a profile in the VoiceBox UI —
`GET /profiles/presets/kokoro` lists every preset voice — and put its name in
`VOICEBOX_PROFILE`.

**The voice falls back three times.** At startup `load_voice()` tries each
engine in quality order and stops at the first that answers:

| | Engine | Where | Cost | Fails over when |
|---|---|---|---|---|
| 1 | **Fish Audio** (British female) | Cloud | Per use | No key, bad key, no API credit, no internet |
| 2 | **VoiceBox** (Apollo Emma) | Local | Free | Server down, profile renamed or missing |
| 3 | **Piper** (`en_GB-jenny_dioco-medium`) | Local | Free | Package missing, model file corrupt |
| 4 | **Windows SAPI** (Zira) | Local | Free | Never — it is the floor |

Whichever wins is named in the overlay at startup, and a rejected engine says
why. If an engine dies *mid-session* — Fish hits a 402 as the credit runs dry,
VoiceBox is closed — that one line is spoken by the next engine down and the
preferred one is retried on the following turn, since the usual causes are
transient. Nothing in this chain can stop Apollo from starting or leave a reply
unspoken.

**Changing the cloud voice.** `FISH_VOICE` is a voice model id from
[fish.audio](https://fish.audio). Search for alternatives with:

```
curl -H "Authorization: Bearer $FISH_API_KEY" \n     "https://api.fish.audio/model?title=<name>&page_size=30&language=en"
```

The default is `a4c68282850b4568bc92749fa2c16815` — a British female voice
tagged *energetic, cheerful, enthusiastic, bright, friendly, expressive*, with
~4.8k generations behind it. Two other English female ones worth hearing:
`e107ce68d2a64e928c3a674781ce9d56` (American, crisp and professional) and
`be321b0d1e0c4558b62001d77a0ab69f` (American, warmer and more conversational).
Look up any id directly with `GET https://api.fish.audio/model/<id>` to check
its title and tags before switching.

**Secrets.** `FISH_API_KEY` lives in `.env`, which `.gitignore` excludes. A
real Windows environment variable of the same name overrides the file, so you
can point a single session at a different key without editing anything.
`assistant.load_env()` reads the file at import — no `python-dotenv` needed.

Piper's own knobs still apply on that fallback path: set `PIPER_VOICE` to any
name from the [Piper voice list](https://huggingface.co/rhasspy/piper-voices)
and delete `voices/` so it re-downloads. `en_GB-alba-medium` is a Scottish
female voice, `en_US-lessac-medium` an American one (still in `voices/` from
before the switch).

**Effort and latency.** There are two effort settings now, deliberately
different:

- Conversation runs at `effort: "low"` (in `ask_claude`), which keeps replies
  fast. That's the right trade for chat.
- Deep research runs at `RESEARCH_EFFORT = "high"`, because thoroughness is the
  entire point of it.

Raising the conversational one to `"high"` makes every ordinary question
slower and dearer, so change that one only if you want it to reason harder on
everything.

---

## Troubleshooting

**"ANTHROPIC_API_KEY is not set"** — you didn't open a new terminal after
`setx`. See Step 2.

**"Your API key was rejected"** — the key is wrong or was deleted. Also check
you have credit in the console; a valid key with a $0 balance fails too.

**Any API error** — the app now prints the API's actual message, error type and
`request_id`, not just the status code. Two you might hit:

- `anthropic-workspace-id is required...` → see Step 2b.
- `anthropic-workspace-id header must be a valid workspace ID` → the ID is set
  but wrong. Re-copy it from the workspace URL; it starts with `wrkspc_`.

The app checks API access at startup with a free request, so configuration
problems show up immediately instead of after you've spoken.

**The hotkey does nothing** — `Ctrl+Alt` is held by some remapping tools, and on
a non-US layout AltGr reports as Ctrl+Alt, so typing an accented character can
open a recording. Change `HOTKEY` to something like `ctrl+alt+j`. Also note
that Windows can't deliver keystrokes to a normal program from windows running
as Administrator unless the assistant is also running as Administrator.

**It transcribes the wrong words** — bump `WHISPER_SIZE` to `small.en`. Also
check Windows is using your headset mic and not a webcam or the Steam virtual
mic: **Settings -> System -> Sound -> Input**.

**No sound comes out** — check the output device in the same Sound settings.
The reply still appears in the transcript, so you can tell whether the failure
is in TTS or earlier in the chain.

**It hears the tail end of nothing / cuts you off** — the recording runs
exactly as long as the key is held. Hold it a beat longer than you think you
need.

**It sounds robotic again** — you have fallen all the way to SAPI, meaning
neither VoiceBox nor Piper loaded. The window notes why when it happens. Check
that VoiceBox is running (`curl http://127.0.0.1:17493/health` should say
`healthy`) and that a profile named `Apollo George` still exists; if Piper is
the problem instead, the voice download was probably interrupted, so delete
`voices/` and restart.

**It sounds American again** — VoiceBox is down and Piper took over. Same
check as above; the overlay note at startup says which voice won.

**It won't open an app you have installed** — it tries the known-apps list,
then `PATH`, then your Start Menu shortcuts. Something installed with no Start
Menu entry and no `PATH` entry can't be found by name. Add it to `KNOWN_APPS`
in `pc_control.py`, or say the full path instead.

**It opened the wrong file** — name matching prefers an exact name, then falls
back to a partial one, searching Desktop, Documents, Downloads, Pictures, Music
and Videos three levels deep. If two files have similar names, give it the full
path.

**It answers from memory instead of searching** — say so explicitly ("search
for...", "look up..."). Claude decides when to search, and it's conservative
about it. If it never searches at all, check whether web search is enabled for
your organisation in the Console.

---

## Cost

At Opus 5 rates ($5 per million input tokens, $25 per million output), the
three things it does cost very different amounts. **Deep research is the one to
watch.**

| What | Roughly | Why |
|---|---|---|
| A spoken question | well under a cent | ~700 tokens of prompt and tool definitions, plus your question and a short answer |
| Opening an app | the same | It's one ordinary turn that happens to call a tool |
| A question that searches | a bit more, plus per-search fees | Search results land in the context, and web searches are billed separately from tokens |
| **Deep research** | **dollars per handful, not cents** | A dozen searches, several full pages pulled into context, `effort: "high"`, and up to 16K output — all in one command |

Those are estimates, not measurements. The per-turn figure is derived from the
prompt's character count rather than a real token count; Anthropic publishes
current web-search pricing at <https://claude.com/pricing>. Measure your own
usage before trusting any of it.

Four things to know:

- **Deep research is easy to trigger by accident.** "Look into that for me"
  is enough. If it's costing more than you'd like, drop `RESEARCH_SEARCHES`
  from `12`, or lower `RESEARCH_EFFORT` from `"high"` to `"medium"`.
- The conversation history grows for as long as the app runs, so a very long
  session gets gradually more expensive per question. Restarting the app clears
  it. Research passes are *not* kept in that history — they run in their own
  conversation precisely so a dozen fetched pages don't ride along on every
  later question. (If history growth becomes a real problem, the fix is
  server-side compaction — ask and I'll wire it in.)
- Whisper is local and free, so listening costs nothing no matter how much you
  talk. **Speech is no longer free**: Fish Audio bills per use, and Fish meters
  API credit separately from the platform credit you buy on fish.audio — a
  paid-up website account can still leave the API at zero. Check it with
  `GET /wallet/self/api-credit`. If it empties, Apollo drops to VoiceBox and
  keeps working, so the failure mode is a worse voice, not a dead assistant.
- **Privacy changed with Fish.** Your microphone audio still never leaves the
  PC — recording and transcription are both local. What leaves is text: your
  transcribed words go to the Claude API, and the text of each reply goes to
  Fish Audio to be spoken. For a fully local setup, clear `FISH_API_KEY` and
  Apollo falls back to VoiceBox on its own.
- Switching `CLAUDE_MODEL` to `claude-sonnet-5` cuts the cost by about 60% and
  you likely won't notice a difference for everyday questions.

You can watch actual spend at <https://console.anthropic.com/settings/usage>.
Setting a spend limit under **Billing** is a good idea while you're
experimenting — and more so now that one sentence can kick off a dozen
searches.

---

## Where to take it next

Done so far: **tools** (opening apps, files and folders), **web search and
deep research**, and **better TTS** (VoiceBox over its local REST API, with
Piper and then SAPI as fallbacks).

Reasonable next steps, roughly by effort:

- **Streaming replies** so it starts speaking before Claude finishes writing.
  This is the biggest remaining win on how fast it *feels*: right now the whole
  answer is written, then synthesised, then played. VoiceBox has a
  `POST /generate/stream` endpoint, so the speaking half is half-built.
- **A wake word** ("Hey Apollo") instead of a hotkey, via `openwakeword`.
  Runs locally, so it costs nothing to try.
- **Interrupting it** — right now `speak()` blocks until the sentence finishes
  and there's no way to cut it off mid-answer. Worth having once replies get
  longer.
- **More tools** — control your music, read your calendar, take a note. The
  tool plumbing is already there; each new one is a schema in `TOOLS` and a
  handler in `_run_tool`.
- **Run it on startup** minimized to the tray, so it's always available.
