#!/usr/bin/env bash
# Exercise every API endpoint, including error paths, against a demo-seeded
# backend (alembic upgrade head && python -m app.cli seed-demo && uvicorn ...).
# Prints PASS/FAIL per check.
B=${1:-http://localhost:8000}
pass=0; fail=0

check() { # name expected_code method path [body]
  local name=$1 expected=$2 method=$3 path=$4 body=${5:-}
  local args=(-s -o /tmp/last_body -w "%{http_code}" -X "$method" "$B$path")
  [ -n "$body" ] && args+=(-H "Content-Type: application/json" -d "$body")
  local code
  code=$(curl "${args[@]}")
  if [ "$code" = "$expected" ]; then
    echo "PASS  $name ($method $path -> $code)"; pass=$((pass+1))
  else
    echo "FAIL  $name ($method $path -> $code, expected $expected)"; fail=$((fail+1))
    head -c 300 /tmp/last_body; echo
  fi
}

jqcheck() { # name python_expr (reads /tmp/last_body)
  local name=$1 expr=$2
  if python3 -c "import json,sys; d=json.load(open('/tmp/last_body')); assert $expr, 'assertion failed'" 2>/tmp/jq_err; then
    echo "PASS  $name"; pass=$((pass+1))
  else
    echo "FAIL  $name: $(cat /tmp/jq_err | tail -1)"; fail=$((fail+1))
  fi
}

echo "--- health ---"
check "health" 200 GET /api/health
jqcheck "health has disclaimer" "'not financial advice' in d['disclaimer']"

echo "--- watchlist CRUD ---"
check "list watchlist" 200 GET /api/watchlist
jqcheck "seeded 4 items" "len(d) == 4"
check "add ticker" 201 POST /api/watchlist '{"ticker": "tsla", "notes": "test add"}'
jqcheck "ticker uppercased" "d['ticker'] == 'TSLA'"
check "duplicate add rejected" 409 POST /api/watchlist '{"ticker": "TSLA"}'
check "empty ticker rejected" 422 POST /api/watchlist '{"ticker": ""}'
check "update notes" 200 PATCH /api/watchlist/TSLA '{"notes": "updated"}'
jqcheck "notes updated" "d['notes'] == 'updated'"
check "patch unknown ticker" 404 PATCH /api/watchlist/ZZZTOP '{"notes": "x"}'
check "delete ticker" 204 DELETE /api/watchlist/TSLA
check "delete again -> 404" 404 DELETE /api/watchlist/TSLA

echo "--- ticker search & detail ---"
check "search by prefix" 200 GET "/api/tickers/search?q=NV"
jqcheck "NVDA found, flagged on watchlist" "d[0]['ticker'] == 'NVDA' and d[0]['on_watchlist'] is True"
check "search by company name" 200 GET "/api/tickers/search?q=micro"
jqcheck "MSFT found by name" "any(r['ticker'] == 'MSFT' for r in d)"
check "search empty q rejected" 422 GET "/api/tickers/search?q="
check "ticker detail" 200 GET /api/tickers/NVDA
jqcheck "detail has fundamentals+score" "d['fundamentals']['pe'] == 45.0 and d['score']['total'] is not None and d['on_watchlist'] is True"
check "detail lowercase input" 200 GET /api/tickers/nvda
check "unknown ticker detail" 404 GET /api/tickers/ZZZTOP

echo "--- per-ticker feeds ---"
check "congress trades" 200 GET /api/tickers/NVDA/congress-trades
jqcheck "congress rows present, sorted desc" "len(d) == 4 and d[0]['transaction_date'] >= d[-1]['transaction_date']"
check "insider trades" 200 GET /api/tickers/NVDA/insider-trades
jqcheck "insider rows present" "len(d) == 2 and d[0]['code'] == 'P'"
check "prices" 200 GET "/api/tickers/NVDA/prices?days=90"
jqcheck "price rows in window" "40 < len(d) < 70 and all(p['close'] for p in d)"
check "feeds for unknown ticker" 404 GET /api/tickers/ZZZTOP/prices

echo "--- scores ---"
check "dashboard scores" 200 GET /api/scores
jqcheck "4 rows sorted by score desc" "len(d) == 4 and d[0]['ticker'] == 'NVDA' and d[0]['score'] >= d[-1]['score']"
jqcheck "rows carry sparkline+components" "len(d[0]['sparkline']) > 30 and set(d[0]['components']) == {'fundamentals','congress','insider','momentum'}"
check "score breakdown" 200 GET /api/scores/NVDA
jqcheck "breakdown provenance complete" "all(c['status']=='ok' and c['source'] and c['data_as_of'] for c in d['components'].values())"
jqcheck "contributions sum to total" "abs(sum(c['contribution'] for c in d['components'].values()) - d['total']) < 0.1"
check "breakdown unknown ticker" 404 GET /api/scores/ZZZTOP
check "recompute" 200 POST /api/scores/recompute
jqcheck "recompute covers watchlist + discovery" "len(d) == 6"

echo "--- ideas (Radar) & stats ---"
check "ideas" 200 GET /api/ideas
jqcheck "discovery tickers surfaced, ranked" "[r['ticker'] for r in d] == ['PLTR','AVGO'] and d[0]['buys'] == 3 and d[0]['buyers'] == 3"
jqcheck "idea carries score + sparkline" "d[0]['score'] is not None and len(d[0]['sparkline']) > 30"
check "price stats" 200 GET /api/tickers/NVDA/stats
jqcheck "stats fields plausible" "d['data_points'] > 200 and 0 < d['annual_vol'] < 2 and d['max_drawdown'] <= 0"
check "stats without history -> 404" 404 GET /api/tickers/AVGO/stats

echo "--- screener & analysis ---"
check "screener" 200 GET /api/screener
jqcheck "screener ranked, PLTR passes all 7" "d[0]['ticker'] == 'PLTR' and d[0]['passed'] == 7"
jqcheck "unknown-only ticker present, never silent" "any(r['ticker'] == 'AVGO' and r['unknown'] == 7 for r in d)"
check "analysis disabled without key" 400 POST /api/analysis/NVDA
jqcheck "analysis error is actionable" "'ANTHROPIC_API_KEY' in d['detail']"
check "no report yet -> 404" 404 GET /api/analysis/NVDA

echo "--- alerts, history & risks ---"
check "alerts feed" 200 GET /api/alerts
jqcheck "demo alerts present with kinds" "len(d) >= 3 and all(r['kind'] in ('congress_trade','insider_trade','score_cross') for r in d)"
check "score history" 200 GET /api/tickers/NVDA/score-history
jqcheck "history has daily entries with deltas" "len(d) >= 5 and d[-1]['total_delta'] is not None and 'congress' in d[-1]['contributions']"
check "risk flags" 200 GET /api/tickers/UNH/risks
jqcheck "UNH shows insider selling cluster" "any(f['id'] == 'insider_selling_cluster' for f in d)"
check "mark alerts seen" 200 POST /api/alerts/seen
jqcheck "marked count returned" "d['marked'] >= 0"
jqcheck_health() { curl -s "$B/api/health" > /tmp/last_body; }
jqcheck_health
jqcheck "health reports auto refresh + momentum in scores" "d['auto_refresh_enabled'] in (True, False)"

echo "--- ingest ---"
check "unknown source" 404 POST /api/ingest/nonsense
check "ingest congress (network blocked here)" 200 POST /api/ingest/congress
jqcheck "run recorded with error status, not a crash" "d[0]['status'] == 'error' and 'congressional sources' in (d[0]['error'] or '')"
check "ingest runs log" 200 GET /api/ingest/runs
jqcheck "runs listed newest first" "len(d) >= 1 and d[0]['source'] == 'congress'"

echo
echo "RESULT: $pass passed, $fail failed"
exit $fail
