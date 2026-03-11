@echo off
setlocal
cd /d "%~dp0"
py -3 scrape_anz_base_rate.py >> logs.txt 2>&1
endlocal
