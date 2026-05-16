@echo off
chcp 65001 >nul 2>&1
cd /d "%~dp0"
echo Starting OmniRouter...
python -m uvicorn backend.main:app --host 0.0.0.0 --port 9090
pause
