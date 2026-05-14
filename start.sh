#!/bin/bash
# NoFishyBusiness Launcher (macOS / Linux)
# Usage: bash start.sh

echo "============================================"
echo " NoFishyBusiness - Starting..."
echo "============================================"
echo ""

# ── Check .env ────────────────────────────────────────────────────────────
if [ ! -f ".env" ]; then
    echo "ERROR: .env file not found."
    echo "Copy .env.example to .env and add your OPENAI_API_KEY."
    exit 1
fi

# ── Seed database ─────────────────────────────────────────────────────────
echo "[1/3] Checking knowledge base..."
python3 knowledge_base/seed.py
echo ""

# ── Start backend in background ───────────────────────────────────────────
echo "[2/3] Starting backend on http://localhost:8000 ..."
python3 -m uvicorn backend.main:app --port 8000 &
BACKEND_PID=$!

# ── Wait for backend ──────────────────────────────────────────────────────
echo "Waiting for backend to start..."
sleep 4

# ── Start frontend ────────────────────────────────────────────────────────
echo "[3/3] Starting frontend..."
echo ""
echo "============================================"
echo " App running at: http://localhost:8501"
echo " Press Ctrl+C to stop both servers."
echo "============================================"
echo ""

# Run frontend in foreground; kill backend when frontend exits
trap "kill $BACKEND_PID 2>/dev/null" EXIT
python3 -m streamlit run frontend/app.py
