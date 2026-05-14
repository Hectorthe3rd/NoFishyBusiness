# NoFishyBusiness Launcher (PowerShell)
# Works on any Windows machine — no hardcoded paths.
# Usage: powershell -ExecutionPolicy Bypass -File start.ps1

Write-Host "============================================" -ForegroundColor Cyan
Write-Host " NoFishyBusiness - Starting..." -ForegroundColor Cyan
Write-Host "============================================"
Write-Host ""

# ── Find a working Python installation ────────────────────────────────────
# Build a list of candidate paths to check, from most to least preferred.
# We test each one by trying to import 'fastapi' — if it works, that's our Python.

$candidates = @()

# Standard user-level installer locations (python.org installer default)
foreach ($ver in @("311","312","310","39","313")) {
    $candidates += "$env:LOCALAPPDATA\Programs\Python\Python$ver\python.exe"
}

# System-wide installer locations
foreach ($ver in @("311","312","310","39","313")) {
    $candidates += "C:\Python$ver\python.exe"
}

# Whatever is on PATH (python3 first, then python)
$candidates += "python3"
$candidates += "python"

$python = $null
foreach ($candidate in $candidates) {
    # For PATH commands (no backslash), check if the command exists first
    if ($candidate -notlike "*\*") {
        $found = Get-Command $candidate -ErrorAction SilentlyContinue
        if (-not $found) { continue }
    } elseif (-not (Test-Path $candidate)) {
        continue
    }

    # Test whether this Python has the required packages
    $result = & $candidate -c "import fastapi" 2>&1
    if ($LASTEXITCODE -eq 0) {
        $python = $candidate
        break
    }
}

if (-not $python) {
    Write-Host "ERROR: Could not find a Python with the required packages." -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix: open a terminal and run:"
    Write-Host "  pip install -r requirements.txt"
    Write-Host ""
    Write-Host "Make sure you installed Python from python.org (not the Windows Store)."
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "Using Python: $python" -ForegroundColor Gray
Write-Host ""

# ── Check .env ────────────────────────────────────────────────────────────
if (-not (Test-Path ".env")) {
    Write-Host "ERROR: .env file not found." -ForegroundColor Red
    Write-Host ""
    Write-Host "Fix: copy .env.example to .env and set your OPENAI_API_KEY:"
    Write-Host "  copy .env.example .env"
    Read-Host "Press Enter to exit"
    exit 1
}

# ── Seed database ─────────────────────────────────────────────────────────
Write-Host "[1/3] Checking knowledge base..." -ForegroundColor Yellow
& $python knowledge_base/seed.py
Write-Host ""

# ── Start backend in new window ───────────────────────────────────────────
Write-Host "[2/3] Starting backend on http://localhost:8000 ..." -ForegroundColor Yellow
Start-Process powershell -ArgumentList "-NoExit", "-Command", "& '$python' -m uvicorn backend.main:app --port 8000"

# ── Wait for backend ──────────────────────────────────────────────────────
Write-Host "Waiting for backend to start..."
Start-Sleep -Seconds 5

# ── Start frontend ────────────────────────────────────────────────────────
Write-Host "[3/3] Starting frontend..." -ForegroundColor Yellow
Write-Host ""
Write-Host "============================================" -ForegroundColor Green
Write-Host " App running at: http://localhost:8501" -ForegroundColor Green
Write-Host " Close both windows to stop." -ForegroundColor Green
Write-Host "============================================"
Write-Host ""
& $python -m streamlit run frontend/app.py
