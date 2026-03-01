#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$HOME/Desktop/efs4_docker"
PIDFILE="$ROOT/.efs4.pids"

# dir:command  (relative to $ROOT)
CMDS=(
  "client_app:python manage.py runserver 8000"
  "efs_sales:python manage.py runserver 0.0.0.0:8001"
  "Efs_profile:python manage.py runserver 0.0.0.0:8002"
  "efs_data:python manage.py runserver 0.0.0.0:8003"
  "efs_operations:python manage.py runserver 0.0.0.0:8004"
  "efs_risk:python manage.py runserver 0.0.0.0:8005"
  "efs_finance:python manage.py runserver 0.0.0.0:8006"
  "efs_drawdowns:python manage.py runserver 0.0.0.0:8007"
  "efs_lms:python manage.py runserver 0.0.0.0:8008"
  "efs_collections:python manage.py runserver 0.0.0.0:8009"
  "efs_settings:python manage.py runserver 0.0.0.0:8013"
  "efs_agents:python manage.py runserver 0.0.0.0:8015"
  "application_aggregate:python manage.py runserver 0.0.0.0:8016"
  "efs_apis:python manage.py runserver 0.0.0.0:8017"
  "efs_data_bureau:python manage.py runserver 0.0.0.0:8018"
  "efs_data_financial:python manage.py runserver 0.0.0.0:8019"
  "efs_data_bankstatements:python manage.py runserver 0.0.0.0:8020"
  "efs_crosssell:python manage.py runserver 0.0.0.0:8021"
  "efs_credit_decision:python manage.py runserver 0.0.0.0:8022"
  "efs_lms_asset_finance:python manage.py runserver 0.0.0.0:8023"
  "efs_lms_invoice_finance:python manage.py runserver 0.0.0.0:8024"
  "efs_lms_overdraft:python manage.py runserver 0.0.0.0:8025"
  "Efs_lms_scf:python manage.py runserver 0.0.0.0:8026"
  "efs_lms_term_loan:python manage.py runserver 0.0.0.0:8027"
  "efs_lms_trade_finance:python manage.py runserver 0.0.0.0:8028"
  "RAG:python manage.py runserver 0.0.0.0:8029"
  "RAG:python manage.py runserver 0.0.0.0:8030"
  "RAG:python manage.py runserver 0.0.0.0:8031"
  "RAG:python manage.py runserver 0.0.0.0:8032"
  "RAG:python manage.py runserver 0.0.0.0:8033"
  "RAG:python manage.py runserver 0.0.0.0:8034"
)

start_all() {
  : > "$PIDFILE"
  for entry in "${CMDS[@]}"; do
    dir="${entry%%:*}"
    cmd="${entry#*:}"

    if [[ ! -d "$ROOT/$dir" ]]; then
      echo "⚠️  Missing directory: $ROOT/$dir — skipping"
      continue
    fi

    echo "▶ Starting $dir: $cmd"
    (
      cd "$ROOT/$dir"
      # run in background but stream logs to this terminal
      exec $cmd &
      echo $! >> "$PIDFILE"
    )
  done
  echo "✅ All available services started. Logs are streaming here."
}

stop_all() {
  if [[ -f "$PIDFILE" ]]; then
    echo "⏹ Stopping services from $PIDFILE..."
    xargs -r kill < "$PIDFILE" || true
    rm -f "$PIDFILE"
    echo "✅ Stopped via PID file."
  else
    echo "⚠️  No PID file. Stopping by port scan (8000–8034)…"
    lsof -ti tcp:8000-8034 | xargs -r kill || true
    echo "✅ Stopped by port scan."
  fi
}

case "${1:-}" in
  up) start_all; wait ;;
  down) stop_all ;;
  restart) stop_all; start_all; wait ;;
  *)
    echo "Usage: $0 {up|down|restart}"
    exit 1
    ;;
esac
