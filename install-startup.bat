@echo off
rem Make Apollo start with Windows.
rem
rem Drops a shortcut in the per-user Startup folder pointing straight at
rem pythonw.exe, not at start.bat - a shortcut to a .bat flashes a console
rem window at every sign-in, and the whole point is that you never see one.
rem
rem Undo with uninstall-startup.bat.
setlocal
cd /d "%~dp0"

if not exist ".\.venv\Scripts\pythonw.exe" (
  echo Could not find .venv\Scripts\pythonw.exe
  echo Run this from the voice-assistant folder, with the venv already set up.
  pause
  exit /b 1
)

powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$s = (New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path ([Environment]::GetFolderPath('Startup')) 'Apollo.lnk'));" ^
  "$s.TargetPath = (Join-Path $PWD '.venv\Scripts\pythonw.exe');" ^
  "$s.Arguments = 'apollo.py';" ^
  "$s.WorkingDirectory = $PWD.Path;" ^
  "$s.Description = 'Apollo voice assistant';" ^
  "$s.Save()"

if errorlevel 1 (
  echo Failed to create the startup shortcut.
  pause
  exit /b 1
)

echo Apollo will now start when you sign in.
echo Starting it now as well...
start "" ".\.venv\Scripts\pythonw.exe" apollo.py
pause
