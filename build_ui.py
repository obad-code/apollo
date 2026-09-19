"""Turn a Claude Design canvas export into the front end Apollo actually runs.

The design is authored in `<name>.dc.html`: markup with `{{ binding }}` holes and
a `class Component extends DCLogic` that fills them. That file is a *demo* - it
answers itself from a canned list of scenes. Shipping it means three things:

  1. loading React, which the canvas host normally supplies;
  2. replacing the demo scene machine with the real backend bridge, so
     `apollo.py` drives the page through `window.apollo.*`;
  3. wrapping the composition in the overlay transform, because Apollo is a
     fullscreen transparent sheet that lives as a small orb until spoken to.

Plus a polish pass over motion, contrast and spacing that belongs to the app
rather than the canvas - see POLISH below.

Run it whenever a new design lands:

    .\\.venv\\Scripts\\python.exe build_ui.py "ADD A CITY.dc.html"

Every edit asserts its own hit count, so a design that has drifted far enough to
break an assumption fails loudly here instead of rendering wrong at runtime.
"""

import os
import re
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "ui", "index.html")
DEFAULT_DESIGN = "ADD A CITY.dc.html"

# Assets the design references by relative path. pywebview's HTTP server roots
# at the page's own directory, so they have to sit under ui/, not beside the
# design file.
ASSETS = [
    ("fonts/Melete-Medium.otf", "ui/fonts/Melete-Medium.otf"),
    ("uploads/ES_User Interface, Motion, Bring Up Hud - Epidemic Sound - 0031-0749.wav",
     "ui/uploads/ES_User Interface, Motion, Bring Up Hud - Epidemic Sound - 0031-0749.wav"),
    ("uploads/ES_User Interface, Click, UI Buttons, Select, Previous - Epidemic Sound.mp3",
     "ui/uploads/ES_User Interface, Click, UI Buttons, Select, Previous - Epidemic Sound.mp3"),
    ("uploads/ES_User Interface, Alert, Notification, Message, Text 01 - Epidemic Sound.mp3",
     "ui/uploads/ES_User Interface, Alert, Notification, Message, Text 01 - Epidemic Sound.mp3"),
    ("uploads/mixkit-dry-pop-up-notification-alert-2356.mp3",
     "ui/uploads/mixkit-dry-pop-up-notification-alert-2356.mp3"),
    ("uploads/mixkit-alien-technology-button-3118.mp3",
     "ui/uploads/mixkit-alien-technology-button-3118.mp3"),
    ("uploads/mixkit-game-liquid-game-hit-3155.mp3",
     "ui/uploads/mixkit-game-liquid-game-hit-3155.mp3"),
]


class Patch:
    """A source string plus an edit log, so every rewrite proves it landed."""

    def __init__(self, text):
        self.text = text
        self.log = []

    def sub(self, old, new, count, label):
        found = self.text.count(old)
        if found != count:
            raise SystemExit(
                f"build_ui: '{label}' expected {count} match(es), found {found}.\n"
                f"  The design has drifted. Looked for:\n    {old[:160]}"
            )
        self.text = self.text.replace(old, new)
        self.log.append(f"{label} ({count})")

    def re_sub(self, pattern, repl, label, flags=0):
        self.text, n = re.subn(pattern, repl, self.text, flags=flags)
        if not n:
            raise SystemExit(f"build_ui: '{label}' matched nothing.")
        self.log.append(f"{label} ({n})")


# ---------------------------------------------------------------------------
# POLISH - motion, contrast and spacing refinements applied on top of the design
# ---------------------------------------------------------------------------

# The canvas leans on Material's standard curve, which is too weak to read as
# deliberate, and on 600-900ms fades. State feedback has to be faster than that:
# the fades carry "Apollo heard you", and anything past ~400ms reads as lag.
# The one long move that stays long is the stage transform - that is the single
# authored moment, and it should have weight.
EASING = """
  :root {
    --ap-ease-out: cubic-bezier(0.23, 1, 0.32, 1);     /* strong ease-out: entrances, fades */
    --ap-ease-stage: cubic-bezier(0.32, 0.72, 0, 1);   /* weighty: the orb <-> full-screen move */
    --ap-ease-io: cubic-bezier(0.77, 0, 0.175, 1);     /* on-screen movement */
  }

  /* The overlay sheet is transparent: the desktop shows through it. Nothing
     here may paint an opaque ground. */
  html, body { background: transparent !important; }

  /* Real answers are paragraphs, not the one-liner the canvas demoes. Step the
     display size down as the answer grows so long replies stay on screen
     without the fit-zoom bottoming out at its 0.72 floor. */
  .ap-answer { font-size: 30px; line-height: 1.34; }

  /* In the 460px panel the display sizes above are far too big, so the whole
     ramp steps down. Same face, same colour, same glow - just sized for the
     space it actually has. */
  [data-ap-scale="panel"] .ap-answer { font-size: 17px; line-height: 1.42; max-width: 100%; }
  [data-ap-scale="panel"] .ap-answer[data-len="m"] { font-size: 15px; }
  [data-ap-scale="panel"] .ap-answer[data-len="l"],
  [data-ap-scale="panel"] .ap-answer[data-len="xl"] {
    font-size: 13px; line-height: 1.5; text-align: left;
    max-height: 40vh; overflow-y: auto;
  }
  [data-ap-scale="panel"] .ap-transcript { font-size: 12px !important; }
  .ap-answer[data-len="m"] { font-size: 25px; line-height: 1.4; }
  /* Past a few lines, centred text is ragged on both edges and slow to read,
     so the long tiers set flush left even though the block stays centred. */
  .ap-answer[data-len="l"] {
    font-size: 21px; line-height: 1.46; max-width: 780px; text-align: left;
  }
  .ap-answer[data-len="xl"] {
    font-size: 17px; line-height: 1.55; max-width: 720px; text-align: left;
    max-height: 46vh; overflow-y: auto; padding-right: 12px;
  }

  /* Browser surfaces belong to the design too. */
  .ap-answer[data-len="xl"]::-webkit-scrollbar { width: 3px; }
  .ap-answer[data-len="xl"]::-webkit-scrollbar-track { background: rgba(255,176,0,0.07); }
  .ap-answer[data-len="xl"]::-webkit-scrollbar-thumb {
    background: rgba(255,176,0,0.34); border-radius: 2px;
  }
  ::selection { background: rgba(255,176,0,0.26); color: #FFE6B8; }

  /* Deliberately does not animate opacity. This runs with fill `both`, and a
     filled animation outranks a plain declaration - animating opacity here
     would pin the note visible and the noteOpacity binding would never win. */
  @keyframes ap-note-in {
    from { transform: translate(-50%, 10px); filter: blur(4px); }
    to   { transform: translate(-50%, 0);    filter: blur(0); }
  }

  /* Reduced motion keeps the state changes legible and drops the travel:
     the orb still becomes the full composition, it just does not fly there. */
  @media (prefers-reduced-motion: reduce) {
    * { animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; }
    [data-ap-stage] { transition-duration: 120ms !important; }
  }
"""

# The idle orb and the note live outside the stage transform, so they stay at
# full size and full legibility whatever scale the composition is at.
NOTE_MARKUP = """
  <div style="position:absolute; left:50%; bottom:38px; z-index:70; transform:translateX(-50%); max-width:min(680px, 78vw); box-sizing:border-box; padding:11px 17px; pointer-events:none; opacity:{{ noteOpacity }}; transition:opacity 260ms var(--ap-ease-out); background:rgba(26,13,0,0.92); border:1px solid rgba(255,176,0,0.26); border-radius:2px; box-shadow:0 6px 30px rgba(0,0,0,0.55), inset 0 0 26px rgba(255,176,0,0.06); animation:ap-note-in 320ms var(--ap-ease-out) both;">
    <span style="display:block; font-size:12.5px; line-height:1.45; font-weight:450; letter-spacing:0.01em; color:#FFC15E; text-wrap:pretty; white-space:pre-wrap;">{{ noteText }}</span>
  </div>
"""

BRIDGE = r"""
  /* --- the real backend bridge ----------------------------------------
     apollo.py drives the page through window.apollo.* (status / turn /
     note / fatal). Everything the canvas used to answer itself with -
     scenes, toggleListen, ask - stays above, unused, so a future feature
     can wire the per-topic cards to live data. */

  registerBridge() {
    window.__apolloInstance = this;
  }

  /* --- what shape the window is ----------------------------------------
     apollo.py sizes the window to one of three shapes and tells the page which
     one it is wearing, so the page renders to fill it rather than scaling a
     whole screen's worth of composition down into a corner.

       orb    a small circle, the resting state - core only
       panel  big enough to read a reply in - core, question, answer
       full   the whole work area - everything, including Lyla and the HUD  */

  isOrb()   { return this.state.mode === 'orb'; }
  isFull()  { return this.state.mode === 'full'; }
  isExpanded() { return !this.isOrb(); }

  applyMode(name) {
    if (name === this.state.mode) return;
    if (name !== 'orb') this.sfx('hud');
    this.setState({ mode: name }, () => { this.initStars(); this.measureFit(); });
  }

  applyStatus(state) {
    clearTimeout(this.t1); clearTimeout(this.t2); clearInterval(this.tick);
    const map = {
      Waking: 'waking', Idle: 'idle', Listening: 'listening',
      Thinking: 'thinking', Speaking: 'response', Error: 'idle'
    };
    const phase = map[state] || 'idle';
    // Tracked on the instance, not read back from state: React batches
    // setState, so two statuses in a row would both still see the old phase.
    // A repeated status is not a new turn - only the change chimes.
    const changed = phase !== this._phase;
    this._phase = phase;
    if (phase === 'listening') {
      if (changed) this.sfx('hud');
      this.setState({ phase, scene: null, transcript: '', answerText: '' });
    } else if (phase === 'thinking') {
      // No chime here. Thinking is entered before the audio has been
      // transcribed, so chiming on it means chiming at silence - at a cough,
      // at a chord pressed by accident. The "heard you" sound belongs to the
      // moment there is actually a transcript, which is applyTurn('You').
      this.setState({ phase });
    } else if (phase === 'response') {
      if (changed) this.playReveal();
      this.setState({ phase });
    } else {
      this.setState({ phase });
    }
  }

  applyTurn(speaker, text) {
    if (speaker === 'You') { this.playHeard(); this.setState({ transcript: text }); }
    else this.setState({ answerText: text });
  }

  applyNote(text, sticky) {
    clearTimeout(this.noteTimer);
    this.setState({ noteText: text, noteVisible: true });
    if (!sticky) {
      this.noteTimer = setTimeout(() => this.setState({ noteVisible: false }), 6000);
    }
  }

  applyFatal(text) {
    this.applyNote(text, true);
    this.setState({ phase: 'idle' });
  }

  dismiss() {
    this.setState({ noteVisible: false });
  }

  /* Long replies need a smaller display size, not a smaller fit-zoom - the
     zoom floors at 0.72 and then simply overflows. */
  answerLen(text) {
    const n = (text || '').length;
    return n > 620 ? 'xl' : n > 300 ? 'l' : n > 120 ? 'm' : 's';
  }

  renderVals() {
    const v = this.designRenderVals();
    const { phase, transcript, answerText, noteVisible, noteText } = this.state;
    const orb = this.isOrb();
    const full = this.isFull();
    const answering = phase === 'thinking' || phase === 'response';

    return Object.assign(v, {
      // The window itself carries the translucency (a uniform alpha; see
      // apollo.py), so the page only decides how dark its own ground is. The
      // orb paints none at all, the panel just enough for amber text to hold
      // against a bright game behind it, the full display a solid ground.
      scrimAlpha: orb ? 0 : full ? 1 : 0.34,

      // The orb is a 210px circle. Nothing but the core fits, and nothing
      // else belongs: this is the shape Apollo wears while you work.
      // The panel is only a little bigger than the orb, so it gets its own
      // tight padding and a small core rather than the full display's.
      stagePad: orb ? '0px'
        : full ? (answering ? '34px 40px 104px' : '104px 40px 132px')
        : '14px 18px 16px',
      coreFrame: orb ? 'min(100vw, 100vh)'
        : full ? (answering ? 'clamp(150px, 22vh, 200px)' : 'min(360px, 38vh)')
        : (answering ? 'clamp(48px, 17vh, 70px)' : 'min(120px, 34vh)'),
      coreArt: answering && !orb ? '185%' : '100%',
      fitScale: orb ? 1 : v.fitScale,
      answerScale: full ? 'full' : 'panel',
      stageWrapRef: this.stageWrapRef,
      coreBoxRef: this.coreBoxRef,

      // Atmosphere belongs to the shapes that have room for it.
      fieldOpacity: orb ? 0 : 1,
      crtOpacity: orb ? 0 : 1,

      // Lyla and the telemetry are the reason to open the full display, and
      // they stand aside while there is an answer to read.
      hudOpacity: full && !answering ? 1 : 0,
      lylaOpacity: full && !answering ? 1 : 0,
      lylaShift: full && !answering ? '0px' : '18px',
      chromeOpacity: orb ? 0 : 1,
      wordOpacity: !orb && !answering ? '1' : '0',
      hintOpacity: full && !answering && phase === 'idle' ? 0.72 : 0,

      // The dock is the canvas's demo prompts, wired to nothing, and the
      // window does not take clicks. Controls that cannot be used are worse
      // than no controls.
      dockOpacity: 0,
      dockPE: 'none',

      statusLabel: phase === 'waking' ? 'Waking'
        : phase === 'listening' ? 'Listening'
        : phase === 'thinking' ? 'Working'
        : phase === 'response' ? 'Speaking'
        : 'Apollo online',

      onCore: (e) => { e.stopPropagation(); },
      onBackdrop: () => this.dismiss(),

      showTranscript: !orb && answering && !!transcript,
      transcript: transcript || '',
      showThinking: !orb && phase === 'thinking',
      showSimple: !orb && phase === 'response' && !!answerText,
      answerText: answerText || '',
      answerLen: this.answerLen(answerText),
      showStock: false, showWeather: false, showCalendar: false,
      showEmail: false, showSearch: false, showTimer: false,

      noteOpacity: noteVisible && !orb ? 1 : 0,
      noteText: noteText || ''
    });
  }
}

window.apollo = {
  status: (state) => { window.__apolloInstance && window.__apolloInstance.applyStatus(state); },
  turn: (speaker, text) => { window.__apolloInstance && window.__apolloInstance.applyTurn(speaker, text); },
  note: (text) => { window.__apolloInstance && window.__apolloInstance.applyNote(text, false); },
  fatal: (text) => { window.__apolloInstance && window.__apolloInstance.applyFatal(text); },
  mode: (name) => { window.__apolloInstance && window.__apolloInstance.applyMode(name); },
};
"""


def build(design_path):
    src = open(design_path, encoding="utf-8").read()
    p = Patch(src)

    # -- 1. React, which the canvas host normally provides -------------------
    p.sub(
        '<script src="./support.js"></script>',
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/react/18.3.1/umd/react.production.min.js"></script>\n'
        '<script src="https://cdnjs.cloudflare.com/ajax/libs/react-dom/18.3.1/umd/react-dom.production.min.js"></script>\n'
        '<script src="./support.js"></script>',
        1, "react umd")

    # -- 1b. somewhere for errors to go -------------------------------------
    # The overlay has no console, no devtools and no title bar. Without this a
    # script error is simply a page that stopped animating, with nothing to
    # look at. apollo.py reads __apErrs when a turn misbehaves.
    p.sub("<script src=\"./support.js\"></script>",
          "<script>\n"
          "window.__apErrs = [];\n"
          "window.addEventListener('error', (e) => {\n"
          "  window.__apErrs.push(String(e.message) + ' @ ' + (e.filename || '?') + ':' + e.lineno);\n"
          "});\n"
          "window.addEventListener('unhandledrejection', (e) => {\n"
          "  window.__apErrs.push('unhandled rejection: ' + String(e.reason));\n"
          "});\n"
          "</script>\n"
          "<script src=\"./support.js\"></script>",
          1, "error trap")

    # -- 2. polish stylesheet ------------------------------------------------
    p.sub("</style>\n</helmet>", EASING + "</style>\n</helmet>", 1, "polish stylesheet")

    # -- 3. motion: strong curves, and state feedback that keeps up ----------
    p.sub("cubic-bezier(.4,0,.2,1)", "var(--ap-ease-out)",
          p.text.count("cubic-bezier(.4,0,.2,1)"), "ease token")
    p.sub("cubic-bezier(.2,.7,.2,1)", "var(--ap-ease-out)",
          p.text.count("cubic-bezier(.2,.7,.2,1)"), "rise ease token")
    for old, new, label in [
        ("transition:opacity 700ms", "transition:opacity 300ms", "chrome fade"),
        ("transition:opacity 900ms", "transition:opacity 380ms", "hint fade"),
        ("transition:opacity 600ms", "transition:opacity 280ms", "hud fade"),
        ("transition:opacity 420ms", "transition:opacity 260ms", "wordmark fade"),
        ("transition:width 800ms var(--ap-ease-out), height 800ms var(--ap-ease-out)",
         "transition:width 620ms var(--ap-ease-stage), height 620ms var(--ap-ease-stage)",
         "core frame"),
        ("transition:padding 700ms var(--ap-ease-out)",
         "transition:padding 620ms var(--ap-ease-stage)", "stage padding"),
        ("animation:ap-rise 620ms", "animation:ap-rise 380ms", "transcript rise"),
        ("animation:ap-rise 700ms", "animation:ap-rise 420ms", "answer rise"),
        ("animation:ap-rise 760ms", "animation:ap-rise 440ms", "card rise"),
    ]:
        p.sub(old, new, p.text.count(old), label)

    # -- 4. contrast: micro-labels below the 4.5:1 floor ---------------------
    # #FFC15E at 42% over the panel ground is ~3:1. 0.62 clears 4.5:1 and still
    # reads as secondary. Only small text is touched; big type is already fine.
    def lift(m):
        size, head, op = float(m.group(1)), m.group(2), float(m.group(3))
        if size <= 12 and op < 0.6:
            return f"font-size:{m.group(1)}px;{head}opacity:{max(op, 0.62):.2f}"
        return m.group(0)

    body, tail = p.text.split("</x-dc>", 1)
    body, n = re.subn(r"font-size:([0-9.]+)px;([^\"]{0,180}?)opacity:(\.[0-9]+)", lift, body)
    p.text = body + "</x-dc>" + tail
    p.log.append(f"contrast lift ({n} scanned)")

    # -- 5. the overlay wrapper ---------------------------------------------
    root_open = ('<div style="position:fixed; inset:0; background:#000; color:#FFC15E; '
                 'overflow:hidden; cursor:default;" onClick="{{ onBackdrop }}">')
    p.sub(root_open,
          '<div style="position:fixed; inset:0; background:rgba(0,0,0,{{ scrimAlpha }}); '
          'color:#FFC15E; overflow:hidden; cursor:default; '
          'transition:background-color 420ms var(--ap-ease-out);" onClick="{{ onBackdrop }}">\n'
          '  <div data-ap-stage data-ap-scale="{{ answerScale }}" '
          'ref="{{ stageWrapRef }}" style="position:absolute; inset:0;">',
          1, "overlay wrapper open")

    # The CRT screen treatment moves outside the wrapper: full-screen when
    # expanded, gone when Apollo is a 150px orb (its inset vignette would
    # otherwise swallow the orb whole).
    crt_start = p.text.index('  <div style="position:absolute; inset:0; pointer-events:none; z-index:60;')
    crt_end = p.text.index("</div>\n\n</x-dc>")
    crt = p.text[crt_start:crt_end]
    if "z-index:65" not in crt:
        raise SystemExit("build_ui: CRT overlay block not where it was expected.")
    crt_wrapped = ('  </div>\n\n'
                   '  <div style="position:absolute; inset:0; pointer-events:none; z-index:60; '
                   'opacity:{{ crtOpacity }}; transition:opacity 380ms var(--ap-ease-out);">\n'
                   + crt.replace("z-index:6", "z-index:1")
                   + '  </div>\n' + NOTE_MARKUP)
    p.text = p.text[:crt_start] + crt_wrapped + p.text[crt_end:]
    p.log.append("crt layer lifted out of transform (1)")

    # -- 5b. at rest, only the core exists ----------------------------------
    # The nebula container paints an opaque `background:#000` across the whole
    # composition. Scaled into the corner that is not an orb, it is a glowing
    # rectangle with hard edges. The full-bleed layers - nebula, dot grid,
    # starfield - therefore fade out at rest and the corner is left as just the
    # core, which is the one thing the idle state is supposed to be.
    p.sub('  <div style="position:absolute; inset:0; pointer-events:none; '
          'overflow:hidden; isolation:isolate; background:#000; '
          'filter:blur(78px); will-change:filter;">',
          '  <div style="position:absolute; inset:0; pointer-events:none; '
          'opacity:{{ fieldOpacity }}; transition:opacity 380ms var(--ap-ease-out);">\n'
          '  <div style="position:absolute; inset:0; pointer-events:none; '
          'overflow:hidden; isolation:isolate; background:#000; '
          'filter:blur(78px); will-change:filter;">',
          1, "field wrapper open")
    p.sub('  <canvas ref="{{ starRef }}" style="position:absolute; inset:0; '
          'width:100%; height:100%; display:block; pointer-events:none;"></canvas>',
          '  <canvas ref="{{ starRef }}" style="position:absolute; inset:0; '
          'width:100%; height:100%; display:block; pointer-events:none;"></canvas>\n'
          '  </div>',
          1, "field wrapper close")

    # -- 5c. two things that outrank the opacity bindings --------------------
    # The hint pulses via a keyframe that animates opacity, and a running
    # animation beats a plain declaration - so `hintOpacity` could never hide
    # it. Pulse the glow instead and let the binding own visibility. The copy
    # was also describing a click that no longer exists: the sheet is
    # click-through, and the only way in is the hotkey.
    p.re_sub(r"@keyframes ap-hint-pulse \{ 0%,100% \{ opacity:\.42; ",
             "@keyframes ap-hint-pulse { 0%,100% { ", "hint pulse keyframe")
    p.re_sub(r"(@keyframes ap-hint-pulse \{[^}]*\} 50% \{ )opacity:1; ",
             r"\1", "hint pulse keyframe 50%")
    p.sub("Click the core to speak, click again to ask",
          "Hold Ctrl+Alt to talk", 1, "hint copy")

    # drawRing writes the wordmark's opacity imperatively on every frame, which
    # overrides the binding outright. Gate it on the same expanded/resting test
    # everything else uses, eased so the wordmark fades rather than pops.
    p.sub("""    if (this.wordRef.current) {
      const wordMax = (ph === 'response' || ph === 'thinking') ? 0 : 1;
      this.wordRef.current.style.opacity = (Math.max(0, 1 - env * 1.6) * wordMax * (1 - (this.envAmt || 0))).toFixed(3);
    }""",
          """    if (this.wordRef.current) {
      const wordMax = (ph === 'response' || ph === 'thinking') ? 0 : 1;
      // At rest Apollo is a 150px orb; the wordmark under it would be six
      // pixels tall, which is noise rather than branding. Ease rather than
      // cut, because this is written every frame and defeats a CSS transition.
      const gate = this.isExpanded() ? 1 : 0;
      this.wordGate = (this.wordGate || 0) + (gate - (this.wordGate || 0)) * 0.12;
      this.wordRef.current.style.opacity = (Math.max(0, 1 - env * 1.6) * wordMax * (1 - (this.envAmt || 0)) * this.wordGate).toFixed(3);
    }""",
          1, "wordmark gate")

    # -- 6. the core box needs a ref so the orb transform can be exact -------
    p.sub('<div style="position:relative; flex:0 0 auto; width:{{ coreFrame }};',
          '<div ref="{{ coreBoxRef }}" style="position:relative; flex:0 0 auto; width:{{ coreFrame }};',
          1, "core box ref")

    # -- 7. the answer is Claude's, not the canvas's ------------------------
    p.sub('<div style="font-size:30px; font-weight:300; letter-spacing:0.02em; color:#FFC15E; '
          'text-align:center; text-wrap:pretty; max-width:820px; '
          'animation:ap-rise 420ms var(--ap-ease-out) both;">'
          'About 78 million kilometres, and closing.</div>',
          '<div class="ap-answer" data-len="{{ answerLen }}" style="font-weight:300; '
          'letter-spacing:0.01em; color:#FFC15E; text-align:center; text-wrap:pretty; '
          'max-width:820px; animation:ap-rise 420ms var(--ap-ease-out) both;">'
          '{{ answerText }}</div>',
          1, "answer text binding")

    # Spacing: the transcript is what you said, the answer is the reply. They
    # are different groups, so the gap between them should not match the gap
    # inside them. Separate generously, group tightly.
    p.sub('<div style="flex:0 0 auto; width:100%; display:flex; flex-direction:column; '
          'align-items:center; gap:22px;">',
          '<div style="flex:0 0 auto; width:100%; display:flex; flex-direction:column; '
          'align-items:center; gap:34px;">',
          1, "answer column rhythm")
    p.sub('<div style="font-size:26px; font-weight:300; letter-spacing:0.02em; color:#FFC15E; '
          'text-align:center; text-wrap:pretty; max-width:760px;',
          '<div class="ap-transcript" style="font-size:19px; font-weight:400; letter-spacing:0.03em; '
          'color:#FFC15E; opacity:.72; text-align:center; text-wrap:pretty; max-width:640px;',
          1, "transcript demoted below the answer")

    # -- 8. the demo's own key handling must not shadow the global hotkey ----
    p.sub("""    this.onKey = (e) => {
      if (e.code === 'Space' && (e.ctrlKey || e.metaKey)) { e.preventDefault(); this.toggleListen(true); }
      if (e.key === 'Escape') this.reset();
      if ((e.key === 'r' || e.key === 'R') && !e.ctrlKey && !e.metaKey) { e.preventDefault(); this.toggleResearch(); }
    };""",
          """    this.onKey = (e) => {
      // The talk chord (Ctrl+Alt, held) is a global Windows hook in
      // assistant.py. If the page also listened for it, a focused overlay
      // would fire the turn twice.
      if (e.key === 'Escape') this.dismiss();
    };""",
          1, "demo keybindings removed")

    # -- 9. register the instance, and keep the orb transform current --------
    p.sub("""  componentDidMount() {
    this.initStars();""",
          """  componentDidMount() {
    this.registerBridge();
    this.initStars();""",
          1, "instance registration")
    p.sub("    this.onResize = () => { this.initStars(); this.measureFit(); };",
          "    this.onResize = () => { this.initStars(); this.measureFit(); };",
          1, "overlay recompute on resize")
    p.sub("""    if (!prevState || prevState.phase !== this.state.phase || prevState.scene !== this.state.scene) this.measureFit();""",
          """    if (!prevState || prevState.phase !== this.state.phase || prevState.scene !== this.state.scene) this.measureFit();
    if (!prevState || prevState.phase !== this.state.phase
        || prevState.mode !== this.state.mode) this.measureFit();""",
          1, "overlay recompute on phase")
    p.sub("""    requestAnimationFrame(() => requestAnimationFrame(() => { this.initStars(); this.measureFit(); }));""",
          """    requestAnimationFrame(() => requestAnimationFrame(() => { this.initStars(); this.measureFit(); }));""",
          1, "overlay first measure")

    # -- 10. idle is a 150px orb: it does not need 60fps or a hidden HUD -----
    p.sub("""  loop = (t) => {
    this.raf = requestAnimationFrame(this.loop);
    this.drawStars(t);
    this.drawRing(t);
    this.drawLyla(t);
    this.drawHud(t);
  };""",
          """  loop = (t) => {
    this.raf = requestAnimationFrame(this.loop);
    // This window never closes, so its resting cost is the cost. At rest the
    // HUD and Lyla are not on screen at all and the core is 150px wide, so
    // half the frames and two of the four draws are pure waste.
    const resting = this.isOrb();
    if (resting && t - (this.lastFrame || 0) < 33) return;
    this.lastFrame = t;
    this.drawStars(t);
    this.drawRing(t);
    if (!resting) { this.drawLyla(t); this.drawHud(t); }
  };""",
          1, "idle frame budget")

    # -- 11. the bridge replaces the demo's renderVals -----------------------
    p.sub("""  renderVals() {
    const { phase, scene, now, edge, timerLeft, fit } = this.state;""",
          """  designRenderVals() {
    const { phase, scene, now, edge, timerLeft, fit } = this.state;""",
          1, "design renderVals renamed")
    p.sub("""  constructor(props) {
    super(props);""",
          """  constructor(props) {
    super(props);
    this.stageWrapRef = React.createRef();
    this.coreBoxRef = React.createRef();""",
          1, "overlay refs")
    p.sub("""    this.state = { phase: 'idle', scene: null, edge: false, now: new Date(), timerLeft: 1500, fit: 1 };""",
          """    this.state = {
      phase: 'waking', scene: null, edge: false, now: new Date(), timerLeft: 1500, fit: 1,
      mode: 'orb',
      transcript: '', answerText: '', noteText: '', noteVisible: false
    };""",
          1, "backend state")

    # The class closes on the last bare `}` before the script tag; everything
    # after it (</script></body></html>) is kept as-is.
    tail_marker = "\n}\n</script>"
    cut = p.text.rfind(tail_marker)
    if cut == -1:
        raise SystemExit("build_ui: the design script does not end where expected.")
    p.text = p.text[:cut] + "\n" + BRIDGE + p.text[cut + len("\n}\n"):]
    p.log.append("backend bridge (1)")

    return p


def main():
    design = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DESIGN
    design_path = design if os.path.isabs(design) else os.path.join(HERE, design)
    if not os.path.exists(design_path):
        raise SystemExit(f"build_ui: no such design: {design_path}")

    for src, dst in ASSETS:
        s, d = os.path.join(HERE, src), os.path.join(HERE, dst)
        if not os.path.exists(s):
            raise SystemExit(f"build_ui: missing asset {src}")
        os.makedirs(os.path.dirname(d), exist_ok=True)
        if not os.path.exists(d) or os.path.getmtime(s) > os.path.getmtime(d):
            shutil.copy2(s, d)

    p = build(design_path)
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    with open(OUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(p.text)

    print(f"built {os.path.relpath(OUT, HERE)} from {os.path.basename(design_path)}")
    for line in p.log:
        print(f"  - {line}")


if __name__ == "__main__":
    main()
