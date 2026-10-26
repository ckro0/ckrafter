@echo off
cd /d "%~dp0"
py -3 repair_finder\server.py
if errorlevel 1 pause
