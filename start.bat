@echo off
setlocal enabledelayedexpansion
title NoFishyBusiness Launcher

echo ============================================
echo  NoFishyBusiness - Starting...
echo ============================================
echo.

REM ── Find a working Python installation ────────────────────────────────────
REM Searches standard installer locations for any Python version that has
REM the required packages installed. Works on any Windows machine.
REM Never picks the Windows Store stub (which has no packages).

set PYTHON=

REM Try standard installer location: C:\Users\<name>\AppData\Local\Programs\Python\
for %%V in (311 312 310 39 313) do (
    if exist "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" (
        "%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe" -c "import fastapi" >nul 2>&1
        if !errorlevel! == 0 (
            if "!PYTHON!" == "" set PYTHON=%LOCALAPPDATA%\Programs\Python\Python%%V\python.exe
        )
    )
)

REM Try system-wide install: C:\Python3xx\
for %%V in (311 312 310 39 313) do (
    if exist "C:\Python%%V\python.exe" (
        "C:\Python%%V\python.exe" -c "import fastapi" >nul 2>&1
        if !errorlevel! == 0 (
            if "!PYTHON!" == "" set PYTHON=C:\Python%%V\python.exe
        )
    )
)

REM Try PATH — python3 first, then python (skip Windows Store stub)
if "!PYTHON!" == "" (
    python3 -c "import fastapi" >nul 2>&1
    if !errorlevel! == 0 set PYTHON=python3
)
if "!PYTHON!" == "" (
    python -c "import fastapi" >nul 2>&1
    if !errorlevel! == 0 set PYTHON=python
)

REM Nothing worked — tell the user what to do
if "!PYTHON!" == "" (
    echo ERROR: Could not find a Python installation with the required packages.
    echo.
    echo Fix: open a terminal and run:
    echo   pip install -r requirements.txt
    echo.
    echo If that still fails, make sure you installed Python from python.org
    echo ^(NOT the Windows Store version^).
    echo.
    pause
    exit /b 1
)

echo Using Python: !PYTHON!
echo.

REM ── Check .env exists ─────────────────────────────────────────────────────
if not exist ".env" (
    echo ERROR: .env file not found.
    echo.
    echo Fix: copy .env.example to .env, then open it and set your OPENAI_API_KEY.
    echo   copy .env.example .env
    echo.
    pause
    exit /b 1
)

REM ── Seed the database ─────────────────────────────────────────────────────
echo [1/3] Checking knowledge base...
"!PYTHON!" knowledge_base/seed.py
echo.

REM ── Start backend in a new window ─────────────────────────────────────────
echo [2/3] Starting backend on http://localhost:8000 ...
start "NoFishyBusiness Backend" cmd /k ""!PYTHON!" -m uvicorn backend.main:app --port 8000"

REM ── Wait for backend to be ready ──────────────────────────────────────────
echo Waiting for backend to start...
timeout /t 5 /nobreak >nul

REM ── Start frontend ────────────────────────────────────────────────────────
echo [3/3] Starting frontend...
echo.
echo ============================================
echo  App running at: http://localhost:8501
echo  Close both terminal windows to stop.
echo ============================================
echo.
"!PYTHON!" -m streamlit run frontend/app.py

endlocal
