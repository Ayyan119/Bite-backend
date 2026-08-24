#!/usr/bin/env bash
# Script to launch Streamlit UI and verify backend

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" >/dev/null 2>&1 && pwd )"
ROOT_DIR="$(dirname "$DIR")"

echo "=== Starting Project Bite Streamlit Test UI ==="

# Activate virtual environment if present
if [ -d "$ROOT_DIR/.venv" ]; then
    source "$ROOT_DIR/.venv/bin/activate"
fi

# Check if FastAPI backend is running on port 8000
if curl -s http://localhost:8000/health > /dev/null; then
    echo "✓ FastAPI backend server is already running on http://localhost:8000"
else
    echo "Starting FastAPI backend server in background..."
    cd "$ROOT_DIR"
    uvicorn app.main:app --host 0.0.0.0 --port 8000 &
    sleep 3
fi

echo "Launching Streamlit application on port 8501..."
streamlit run "$DIR/app.py" --server.port 8501 --server.address 0.0.0.0
