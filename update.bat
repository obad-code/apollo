@echo off
rem Double-click: gets the latest Apollo and installs what the Shorts need.
cd /d "%~dp0"
git pull origin claude/upbeat-bell-jsj33h
".\.venv\Scripts\python.exe" -m pip install numpy pillow edge-tts imageio-ffmpeg google-api-python-client google-auth-oauthlib
echo.
echo Done. Now close Apollo and open it again.
pause
