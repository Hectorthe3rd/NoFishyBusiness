@echo off
setlocal enabledelayedexpansion
title NoFishyBusiness Evaluation Suite

REM ── Find a working Python installation ────────────────────────────────────
REM Uses the same detection logic as start.bat — finds whichever Python has
REM the required packages installed, regardless of what's on PATH.

set PYTHON=

for %%V in (311 312 310 39 313) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import requests" >nul 2>&1
        if !errorlevel! == 0 (
            if "!PYTHON!" == "" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe
        )
    )
)

for %%V in (311 312 310 39 313) do (
    if exist "C:\Python%%V\python.exe" (
        "C:\Python%%V\python.exe" -c "import requests" >nul 2>&1
        if !errorlevel! == 0 (
            if "!PYTHON!" == "" set PYTHON=C:\Python%%V\python.exe
        )
    )
)

if "!PYTHON!" == "" (
    python3 -c "import requests" >nul 2>&1
    if !errorlevel! == 0 set PYTHON=python3
)
if "!PYTHON!" == "" (
    python -c "import requests" >nul 2>&1
    if !errorlevel! == 0 set PYTHON=python
)

if "!PYTHON!" == "" (
    echo ERROR: Could not find a Python installation with the required packages.
    echo Run:  pip install -r requirements.txt
    pause
    exit /b 1
)

REM ── Run eval.py, passing through any arguments (e.g. --live, --report) ────
"!PYTHON!" eval/eval.py %*

endlocal
