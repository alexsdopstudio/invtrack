#!/usr/bin/env bash
# run-live.sh — setup + ingestione dati REALI + avvio backend/frontend, in un comando.
#
# Uso:
#   ./run-live.sh                   # watchlist di default (NVDA AAPL MSFT), scan insider OFF
#   ./run-live.sh TSLA AMD PLTR     # scegli tu i ticker da tracciare
#   ./run-live.sh --with-scan       # includi anche la scansione insider market-wide (~30 min)
#
# Per i dati DEMO offline (nessuna rete) usa invece:
#   cd backend && .venv/bin/python -m app.cli seed-demo
#
# NB: la SEC/Senate/Yahoo vanno interrogate dalla TUA macchina — non da una
# sandbox con egress bloccato. Se una fonte fallisce, l'output qui sotto te lo
# dice per-sorgente e le altre continuano comunque.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND="$ROOT/backend"
FRONTEND="$ROOT/frontend"
PY="$BACKEND/.venv/bin/python"

# --- argomenti -------------------------------------------------------------
WITH_SCAN=0
TICKERS=()
for arg in "$@"; do
  case "$arg" in
    --with-scan) WITH_SCAN=1 ;;
    -h|--help)   grep '^#' "$0" | grep -v '^#!' | sed 's/^# \{0,1\}//'; exit 0 ;;
    -*)          echo "Flag sconosciuto: $arg" >&2; exit 1 ;;
    *)           TICKERS+=("$(echo "$arg" | tr '[:lower:]' '[:upper:]')") ;;
  esac
done
[ ${#TICKERS[@]} -eq 0 ] && TICKERS=(NVDA AAPL MSFT)

# --- 1. .env ---------------------------------------------------------------
echo "==> Controllo .env"
if [ ! -f "$ROOT/.env" ]; then
  echo "    Manca .env — copio .env.example. IMPOSTA SEC_EDGAR_USER_AGENT prima di continuare."
  cp "$ROOT/.env.example" "$ROOT/.env"
fi
if ! grep -qE '^SEC_EDGAR_USER_AGENT=.+@' "$ROOT/.env"; then
  echo "    ⚠️  SEC_EDGAR_USER_AGENT (nome + email) non impostato nel .env: la SEC può"
  echo "        rifiutare le richieste. Continuo comunque tra 3s (Ctrl+C per fermare)…"
  sleep 3
fi

# --- 2. setup backend ------------------------------------------------------
if [ ! -x "$PY" ]; then
  echo "==> Setup backend (venv + dipendenze + migration)"
  ( cd "$BACKEND" && ./setup.sh )
else
  echo "==> Applico eventuali migration nuove"
  ( cd "$BACKEND" && .venv/bin/alembic upgrade head )
fi

# --- 3. watchlist ----------------------------------------------------------
echo "==> Watchlist: ${TICKERS[*]}"
( cd "$BACKEND" && WATCHLIST="${TICKERS[*]}" "$PY" - <<'PYEOF'
import os
from app.db import SessionLocal, Base, engine
from app.models import WatchlistItem

Base.metadata.create_all(engine)
tickers = os.environ["WATCHLIST"].split()
with SessionLocal() as db:
    added = 0
    for t in tickers:
        if not db.query(WatchlistItem).filter_by(ticker=t).first():
            db.add(WatchlistItem(ticker=t)); added += 1
    db.commit()
    print(f"    {added} nuovi ticker aggiunti ({len(tickers)} richiesti)")
PYEOF
)

# --- 4. ingestione dati reali ---------------------------------------------
echo "==> Ingestione dati reali (tickers → congress → insider → fundamentals → prices)"
if [ "$WITH_SCAN" -eq 0 ]; then
  export INSIDER_SCAN_ENABLED=false
  echo "    (scan insider market-wide OFF — passa --with-scan per includerla, ~30 min)"
fi
# La CLI isola i fallimenti per-sorgente e stampa lo stato di ognuna; non abortisce
# se una fonte va giù (es. House, che non ha una fonte gratuita live).
( cd "$BACKEND" && .venv/bin/python -m app.cli ingest all )

# --- 5. avvio server -------------------------------------------------------
echo "==> Avvio backend (:8000) + frontend (:5173)"
if [ ! -d "$FRONTEND/node_modules" ]; then
  ( cd "$FRONTEND" && npm install )
fi

cleanup() { echo; echo "==> Arresto…"; kill "${BACK_PID:-}" "${FRONT_PID:-}" 2>/dev/null || true; }
trap cleanup EXIT INT TERM

( cd "$BACKEND"  && exec .venv/bin/uvicorn app.main:app --port 8000 ) & BACK_PID=$!
( cd "$FRONTEND" && exec npm run dev )                                & FRONT_PID=$!

sleep 2
echo
echo "    Backend:  http://localhost:8000/api/health"
echo "    Frontend: http://localhost:5173   ← apri questo nel browser"
echo "    Stato ingestione: http://localhost:8000/api/ingest/runs"
echo "    (Ctrl+C per fermare tutto)"
wait
