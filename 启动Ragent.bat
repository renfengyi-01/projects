@echo off
rem ============================================================
rem PERSONAL LOCAL LAUNCHER - NOT part of the course project.
rem
rem This script starts a local copy of the author's own Ragent
rem from an absolute path on the author's machine. It is kept
rem only as personal convenience: it is NOT required to run
rem anything in this repository, and the paths below will not
rem exist on other machines. Safe to delete.
rem ============================================================
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d D:\office
"C:\Users\35967\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 "C:\Users\35967\Agent\Ragent\main.py"
echo.
pause >nul
