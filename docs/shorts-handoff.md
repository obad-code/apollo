# Shorts pipeline - handoff for the next session (n8n / best-of-breed services)

## Where things stand (Oct 2026)
Everything runs inside Apollo, in Python, free by default. Quality was judged "not good enough yet"
by the owner, mainly: voice (robotic), image detail (flat vector props vs photographic objects in the
reference thumbnails), animation/motion. Plan: try the best service for each step BY HAND first, then
automate the winners in n8n.

## The steps and the knob for each (all in shorts.py unless noted)
| step | free default | paid upgrade (env var) |
|---|---|---|
| topic / niche | Google Trends RSS + LLM (autopost.py, niche.py) | writer below |
| script writer | Gemini via lyla.think | `SHORTS_WRITER=claude`, `SHORTS_CLAUDE_MODEL=claude-opus-5-5` (default Sonnet) |
| voice | Edge TTS | `SHORTS_VOICE_ENGINE=gemini` (+`SHORTS_GEMINI_VOICE`) or `elevenlabs` (+`ELEVENLABS_API_KEY`, `SHORTS_ELEVEN_VOICE`) |
| pictures | drawn in code: flat vector hero + 23 places (shorts_scenes.py, shorts_hero.py) | `SHORTS_IMAGES=gemini` (a picture per scene, shorts_art.py); `SHORTS_OBJECTS=gemini` (clean photographic objects on white, cut out and cached, shorts_objects.py) |
| sound | synthesized whoosh/pop/ding/boom + place ambience (shorts_sfx.py); no music by choice | - |
| edit | one continuous render with real transitions + loudnorm | - |
| post | youtube_upload.py (YouTube Data API), Telegram bot to approve (telegram_bot.py, autopost.py) | - |

Other env: `SHORTS_COUNT` (2/day), `SHORTS_POST_ALL`, `SHORTS_WAIT_HOURS`, `SHORTS_STYLE=ink|vector`, `SHORTS_GLASSES`,
`SHORTS_IMAGE_MAX`, `SHORTS_REFINE=0` (skip the editor pass). Build stamp: `shorts.VERSION`.

## Tools for judging output
- `watch.py <youtube link or mp4>` -> sheet.png + report.txt (pace, loudness, captions) to send to Claude.
- every Short gets `... preview.png` (16 frames).

## Research notes: docs/shorts-playbook.md. Reference master prompt (wealth POV): owner has POV_WEALTH_MASTER_SYSTEM.md.

## Plan for the n8n session
1. Owner tries each service by hand with ONE fixed script and sends results: voice (ElevenLabs vs Gemini vs Edge),
   pictures (Gemini / others), motion (an image-to-video service, if any is worth it).
2. Pick the winners; then build the n8n workflow: Schedule -> topics (Trends) -> script (Claude) -> voice -> pictures ->
   motion -> render -> Telegram approval -> YouTube upload. n8n imports workflows as JSON.
3. The renderer (Python + FFmpeg) stays in Apollo; n8n calls it (Execute Command node on the same machine, or a small
   HTTP endpoint). n8n should run where it can stay on (a small server) if the laptop is not always on.
4. Secrets only in environment variables / n8n credentials - never in chat.
