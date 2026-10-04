@echo off
rem Double-click: make ONE Short, save it, open its folder. Nothing is posted, nothing else runs.
cd /d "%~dp0"
set /p TOPIC=What should it be about? (Enter = LYLA chooses): 
".\.venv\Scripts\python.exe" -c "import os,shorts; r=shorts.make(topic=os.environ.get('TOPIC','')); print('Saved:', r['path']); os.startfile(os.path.dirname(r['path']))"
echo.
pause
