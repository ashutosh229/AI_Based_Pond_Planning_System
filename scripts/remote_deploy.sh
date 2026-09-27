#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:?Usage: remote_deploy.sh <app_dir>}"
cd "$APP_DIR"

echo "[deploy] Pulling latest main..."
git fetch origin main
git reset --hard origin/main

echo "[deploy] Installing backend dependencies..."
cd backend
if [ ! -d venv ]; then
  python3 -m venv venv
fi
source venv/bin/activate
pip install -q -r requirements.txt

PID_DIR="$APP_DIR/backend/.pids"
mkdir -p "$PID_DIR"

stop_if_running() {
  local pid_file="$1"
  if [ -f "$pid_file" ]; then
    local pid
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
      echo "[deploy] Stopping PID $pid ($pid_file)..."
      kill "$pid"
      sleep 2
      kill -0 "$pid" 2>/dev/null && kill -9 "$pid" || true
    fi
    rm -f "$pid_file"
  fi
}

echo "[deploy] Restarting backend (port 3000)..."
stop_if_running "$PID_DIR/backend.pid"
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 3000 \
  > "$APP_DIR/backend/backend.log" 2>&1 &
echo $! > "$PID_DIR/backend.pid"

echo "[deploy] Restarting db-server (port 4000)..."
stop_if_running "$PID_DIR/db_server.pid"
SQLITE_DB_PATH="$APP_DIR/backend/pond_runs.db" DB_SERVER_PORT=4000 \
  nohup python3 app/db_server.py \
  > "$APP_DIR/backend/db_server.log" 2>&1 &
echo $! > "$PID_DIR/db_server.pid"

sleep 3

echo "[deploy] Verifying health..."
curl -sf http://localhost:3000/health || { echo "[deploy] backend health check FAILED"; exit 1; }
curl -sf http://localhost:4000/health || { echo "[deploy] db-server health check FAILED"; exit 1; }

echo "[deploy] Deployment successful."