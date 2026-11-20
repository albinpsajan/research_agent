@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  HackathonIQ - local multi-agent research
echo ============================================
echo.

where python >nul 2>nul
if errorlevel 1 (
    echo ERROR: Python is not on PATH.
    echo Install Python 3.11+ and enable "Add Python to PATH".
    pause
    exit /b 1
)

echo Checking environment...
python -m src.cli check
echo.

echo Starting Streamlit at http://localhost:8501
echo Press Ctrl+C in this window to stop.
echo.
python -m streamlit run ui/app.py --server.port 8501 --browser.gatherUsageStats false

if errorlevel 1 (
    echo.
    echo The application exited with an error. See data\logs\hackathoniq.log
    pause
)
endlocal
