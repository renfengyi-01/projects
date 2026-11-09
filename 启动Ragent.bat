@echo off
chcp 65001 >nul
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8
cd /d D:\office
"C:\Users\35967\AppData\Local\Programs\Python\Python313\python.exe" -X utf8 "C:\Users\35967\Agent\Ragent\main.py"
echo.
pause >nul
