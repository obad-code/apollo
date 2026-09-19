@echo off
rem Stop Apollo starting with Windows. Does not quit a running copy - use the
rem tray icon, or Ctrl+Alt+Shift+Q, for that.
setlocal
powershell -NoProfile -ExecutionPolicy Bypass -Command ^
  "$p = Join-Path ([Environment]::GetFolderPath('Startup')) 'Apollo.lnk';" ^
  "if (Test-Path $p) { Remove-Item $p; 'Removed the startup shortcut.' } else { 'No startup shortcut was installed.' }"
pause
