@echo off
setlocal
cd /d "%~dp0"
where py >nul 2>&1
if not errorlevel 1 (
    py -3 "%~dp0start.py" %*
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo Install Python 3.12 or newer from python.org, then reopen this launcher.
        pause
        exit /b 1
    )
    python "%~dp0start.py" %*
)
if errorlevel 1 (
    echo Greenloop could not start. See the message above.
    pause
    exit /b 1
)
