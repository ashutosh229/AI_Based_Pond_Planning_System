#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${1:?Usage: remote_deploy_frontend.sh <app_dir>}"
cd "$APP_DIR"

echo "[deploy] Pulling latest main..."
git fetch origin main
git reset --hard origin/main

echo "[deploy] Installing frontend dependencies..."
cd frontend
npm ci

echo "[deploy] Building..."
npm run build

PID_DIR="$APP_DIR/frontend/.pids"
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

echo "[deploy] Restarting frontend (port 4000)..."
stop_if_running "$PID_DIR/frontend.pid"
nohup npx serve -s dist -l 4000 \
  > "$APP_DIR/frontend/frontend.log" 2>&1 &
echo $! > "$PID_DIR/frontend.pid"

sleep 3

echo "[deploy] Verifying health..."
curl -sf http://localhost:4000/ >/dev/null || { echo "[deploy] frontend health check FAILED"; exit 1; }

echo "[deploy] Deployment successful."