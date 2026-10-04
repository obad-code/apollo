# Apollo - rules for Claude

Apollo is a Windows voice assistant: Python backend (`apollo.py`), a pywebview display in
`ui/full/`, and the native GDI+ Mini Apollo overlay in `orb.py`. The user runs it on their PC at
`C:\Users\Admin\Desktop\voice-assistant` and gets changes with `update.bat`.

## Talking with the user
- Reply in Gulf Arabic. Plain words, short exact steps (`update.bat`, PowerShell at the path
  above, `.\.venv\Scripts\python.exe` for Python).
- Say honestly what was tested and what was not (much here only runs on Windows).

## The user's rules - never break these
- **Make no decision that is not yours.** Do exactly what was asked. When a choice belongs to
  the user (design, scope, paying, which model, what runs by itself), ask first.
- Follow the user's designs exactly.
- Do not change Mini Apollo's look. Do not change the idle gradient.
- Secrets never go in chat or in code: keys, tokens and passwords live only in `setx` env vars.
  The email address is config only (`APOLLO_SMTP_USER`), never hardcoded.
- Do not use the user's cookies or get around YouTube's bot checks.
- Shorts are made only when the user asks; nothing posts by itself
  (`SHORTS_AUTO` and `SHORTS_AUTOPOST` stay off).
- Apollo's voice stays on the free `GEMINI_API_KEY`; the crew uses
  `GEMINI_CREW_KEY` when set, falling back to `GEMINI_API_KEY`.
- Fonts: Inter (Latin) and IBM Plex Sans Arabic (Arabic). Thmanyah is not allowed (licence).
- Parked work is in `docs/next.md` - do not start it unless the user says so.

## Working
- Run the tests for what you change (`.claude/skills/win-check` runs them off Windows).
  Known Windows-only failures off Windows: overlay_paint, fonts, overlay_gil, clips, scanner,
  scan_drop, desk_tabs, start_log.
- Do not leave screenshots or scratch files in the repo.
- Commit and push to the branch you were given; no pull requests unless asked.
