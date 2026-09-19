@echo off
rem Launch Apollo as a background overlay.
rem
rem pythonw.exe has no console, so nothing but the overlay itself appears, and
rem `start` lets this script exit immediately instead of sitting there for the
rem life of the app - the console it runs in only flashes.
rem
rem Apollo holds a single-instance lock, so running this twice is harmless: the
rem second copy notices the first and exits.
rem
rem To debug a startup problem, run this instead and watch the output:
rem     .\.venv\Scripts\python.exe apollo.py
cd /d "%~dp0"
start "" ".\.venv\Scripts\pythonw.exe" apollo.py
