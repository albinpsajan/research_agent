@echo off
setlocal
cd /d "%~dp0"

echo ============================================
echo  HackathonIQ - local multi-agent research
echo ============================================
echo.

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_EXE=.venv\Scripts\python.exe"
) else (
    where python >nul 2>nul
    if errorlevel 1 (
        echo ERROR: Python is not on PATH.
        echo Install Python 3.11+ and enable "Add Python to PATH".
        pause
        exit /b 1
    )
    set "PYTHON_EXE=python"
)

echo Checking environment...
"%PYTHON_EXE%" -m src.cli check
echo.

echo Starting Streamlit at http://localhost:8501
echo Press Ctrl+C in this window to stop.
echo.
"%PYTHON_EXE%" -m streamlit run ui/app.py --server.port 8501 --browser.gatherUsageStats false --client.showSidebarNavigation false

if errorlevel 1 (
    echo.
    echo The application exited with an error. See data\logs\hackathoniq.log
    pause
)
endlocal
