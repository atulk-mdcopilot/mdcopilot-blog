#!/usr/bin/env bash
# shellcheck disable=SC2016  # jq filters reference $variables inside single quotes on purpose
# Phase 1 acceptance run for mdcopilot-blog (docs/blog-agent/IMPLEMENTATION_PLAN.md, Phase 1 "Acceptance").
#
# Host tools: docker (with compose), curl, openssl, and jq. A pinned jq container is used if jq is missing.
# Never reads or prints .env. The two throwaway accounts get passwords generated here. Those
# passwords live only in environment variables and are passed to containers by variable name.
#
# Usage (from anywhere):
#   scripts/acceptance/phase1.sh                 # full run
#   SKIP_SUITES=1 scripts/acceptance/phase1.sh   # skip pytest / vitest / lint / build (quicker re-run)
#
# Side effects:
#   - builds images and starts the stack (docker compose up -d --wait), then recreates api and worker
#     so the log checks see only this run's logs
#   - creates 2 users (acceptance-*-<timestamp>@example.test) and deactivates them at the end
#   - creates 4 mock runs (one of them from a real Chromium browser)
#   - runs throwaway curl and Playwright containers on the compose network; the Playwright container
#     installs playwright@1.63.0 from the npm registry inside itself
#   - recreates the worker twice: once with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=15, once back at 0
#   - kills the worker once
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

CURL_IMAGE="curlimages/curl:8.22.0"
JQ_IMAGE="ghcr.io/jqlang/jq:1.8.1"
BROWSER_IMAGE="mcr.microsoft.com/playwright:v1.63.0-noble"
PLAYWRIGHT_NPM="playwright@1.63.0"
KILL_DELAY_SECONDS=15
SPOOF_IP="203.0.113.7"
RUN_TAG="$(date +%Y%m%d%H%M%S)"
P1_ADMIN_EMAIL="acceptance-admin-${RUN_TAG}@example.test"
P1_VIEWER_EMAIL="acceptance-viewer-${RUN_TAG}@example.test"
export P1_ADMIN_EMAIL P1_VIEWER_EMAIL

PASS_COUNT=0
WARN_COUNT=0
DELAY_CHANGED=0
API=""
WEB=""

TMPD="$(mktemp -d "${TMPDIR:-/tmp}/mdcb-phase1.XXXXXX")"
chmod 700 "$TMPD"
umask 077

step() { printf '\n==> %s\n' "$*"; }
ok() { PASS_COUNT=$((PASS_COUNT + 1)); printf '  PASS  %s\n' "$*"; }
info() { printf '  ....  %s\n' "$*"; }
warn() { WARN_COUNT=$((WARN_COUNT + 1)); printf '  WARN  %s\n' "$*"; }
fail() { printf '  FAIL  %s\n' "$*" >&2; exit 1; }

# Mask anything that looks like a DB URL password or a provider key before it reaches the terminal.
mask() { sed -E -e 's#(postgres(ql)?(\+psycopg)?://[^:/@ ]+:)[^@ ]*@#\1***@#g' -e 's/(sk-|AIza)[A-Za-z0-9_-]{4,}/\1****/g'; }

# Remove terminal colour codes (portable across BSD and GNU sed).
strip_ansi() { sed "s/$(printf '\033')\\[[0-9;]*m//g"; }

if command -v jq >/dev/null 2>&1; then
  jqr() { jq "$@"; }
else
  jqr() { docker run --rm -i "$JQ_IMAGE" "$@"; }
fi

# Run SQL in the db container as the app's own role (local socket, no password).
sql() {
  docker compose exec -T db sh -c 'psql -X -q -v ON_ERROR_STOP=1 -At -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<<"$1"
}

snapshot_logs() {
  docker compose logs --no-color --timestamps api worker >>"$TMPD/logs.txt" 2>&1 || true
}

cleanup() {
  local status=$?
  set +e
  if [ "$DELAY_CHANGED" = 1 ]; then
    info "restoring BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 on the worker"
    if ! BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 docker compose up -d --no-deps --wait worker >/dev/null 2>&1; then
      printf '  WARN  could not restore the worker; run: docker compose up -d --no-deps worker\n' >&2
    fi
  fi
  if [ -n "$API" ]; then
    local who
    for who in admin viewer; do
      if [ -s "$TMPD/$who.jar" ]; then
        curl -sS -o /dev/null -b "$TMPD/$who.jar" -X POST -H "Origin: $API" -H "@$TMPD/$who.csrf" \
          "$API/api/auth/logout" >/dev/null 2>&1
      fi
    done
    # The API cannot deactivate the calling admin, so the throwaway accounts are closed in SQL.
    sql "update app.users set is_active = false where email like 'acceptance-%@example.test' and is_active" >/dev/null 2>&1
  fi
  rm -rf "$TMPD"
  unset P1_ADMIN_PASSWORD P1_VIEWER_PASSWORD
  echo
  if [ "$status" -eq 0 ]; then
    echo "PHASE 1 ACCEPTANCE: PASS (${PASS_COUNT} checks, ${WARN_COUNT} warnings)"
  else
    echo "PHASE 1 ACCEPTANCE: FAIL (${PASS_COUNT} checks passed before the failure)"
  fi
  exit "$status"
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# ---------------------------------------------------------------------------------------------
# HTTP helpers. Host calls go straight to the api port, so Origin is the api's own origin.
# A request's body is written to $TMPD/body and the HTTP status is printed.
# ---------------------------------------------------------------------------------------------
api_call() { # api_call <who> <method> <path> [json-body]
  local who="$1" method="$2" path="$3" body="${4-}"
  local args=(-sS -o "$TMPD/body" -w '%{http_code}' -b "$TMPD/$who.jar" -c "$TMPD/$who.jar" -X "$method" -H "Origin: $API")
  if [ -s "$TMPD/$who.csrf" ]; then args+=(-H "@$TMPD/$who.csrf"); fi
  if [ -n "$body" ]; then args+=(-H 'Content-Type: application/json' --data-binary "$body"); fi
  curl "${args[@]}" "$API$path"
}

body_snippet() { head -c 400 "$TMPD/body" | mask; }

expect_status() { # expect_status <label> <expected> <actual> [--quiet]
  if [ "$3" = "$2" ]; then
    ok "$1 (HTTP $3)"
  elif [ "${4-}" = "--quiet" ]; then
    fail "$1: expected HTTP $2, got $3"
  else
    fail "$1: expected HTTP $2, got $3; body: $(body_snippet)"
  fi
}

expect_problem() { # expect_problem <label> <expected-status> <actual-status> <expected-title>
  local title
  title="$(jqr -r '.title // empty' <"$TMPD/body" 2>/dev/null || true)"
  if [ "$3" = "$2" ] && [ "$title" = "$4" ]; then
    ok "$1 (HTTP $3, \"$title\")"
  else
    fail "$1: expected HTTP $2 \"$4\", got HTTP $3 \"$title\""
  fi
}

login() { # login <who> <email> <password-variable-name>
  # Every login also sends a forged X-Forwarded-For. The check after the CSRF probe proves that the api
  # records the TCP peer, not this header.
  local who="$1" email="$2" pw_var="$3" code
  : >"$TMPD/$who.jar"
  : >"$TMPD/$who.csrf"
  code="$(printf '{"email":"%s","password":"%s"}' "$email" "${!pw_var}" |
    curl -sS -o "$TMPD/body" -w '%{http_code}' -c "$TMPD/$who.jar" -H "Origin: $API" \
      -H "X-Forwarded-For: $SPOOF_IP" -H 'Content-Type: application/json' --data-binary @- "$API/api/auth/login")"
  expect_status "login as $who" 200 "$code"
  printf 'X-CSRF-Token: %s\n' "$(jqr -r '.csrfToken' <"$TMPD/body")" >"$TMPD/$who.csrf"
  jqr -r '.user.id' <"$TMPD/body" >"$TMPD/$who.id"
  [ "$(jqr -r '.user.role' <"$TMPD/body")" = "$who" ] || fail "login as $who: unexpected role in the session response"
}

require_uuid() { # require_uuid <label> <value>
  case "$2" in
    "" | *[!0-9a-f-]*) fail "$1: not a UUID: $2" ;;
  esac
}

create_run() { # create_run <who> -> prints the new run id (caller checks the status file)
  local code
  code="$(api_call "$1" POST /api/blog-agent/runs '{}')"
  printf '%s' "$code" >"$TMPD/create.status"
  jqr -r '.id // empty' <"$TMPD/body" 2>/dev/null || true
}

wait_for_run() { # wait_for_run <who> <run-id> <timeout-seconds>; leaves the detail in $TMPD/run.json
  local who="$1" run_id="$2" timeout="$3" start code status
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    cp "$TMPD/body" "$TMPD/run.json"
    status="$(jqr -r '.status' <"$TMPD/run.json")"
    case "$status" in
      SUCCEEDED) return 0 ;;
      FAILED | CANCELLED)
        fail "run $run_id ended $status; steps: $(jqr -c '[.steps[] | {stepName, status, tries, error}]' <"$TMPD/run.json" | mask)"
        ;;
    esac
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "run $run_id is still $status after ${timeout}s"
    fi
    sleep 1
  done
}

wait_for_step_running() { # wait_for_step_running <who> <run-id> <step-name> <timeout-seconds>
  local who="$1" run_id="$2" step_name="$3" timeout="$4" start code running status
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    running="$(jqr -r --arg s "$step_name" '[.steps[] | select(.stepName == $s and .status == "RUNNING")] | length' <"$TMPD/body")"
    if [ "$running" -ge 1 ]; then
      return 0
    fi
    status="$(jqr -r '.status' <"$TMPD/body")"
    case "$status" in
      SUCCEEDED | FAILED | CANCELLED) fail "run $run_id reached $status before $step_name was seen RUNNING" ;;
    esac
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "$step_name was not RUNNING within ${timeout}s (run status $status)"
    fi
    sleep 0.5
  done
}

wait_for_steps_settled() { # wait_for_steps_settled <who> <run-id> <timeout-seconds>; refreshes $TMPD/run.json
  # finish_step marks the run SUCCEEDED before its mock delay, so its step row can still be RUNNING.
  local who="$1" run_id="$2" timeout="$3" start code running
  start="$(date +%s)"
  while :; do
    code="$(api_call "$who" GET "/api/blog-agent/runs/$run_id")"
    [ "$code" = 200 ] || fail "GET run $run_id returned HTTP $code"
    cp "$TMPD/body" "$TMPD/run.json"
    running="$(jqr -r '[.steps[] | select(.status == "RUNNING")] | length' <"$TMPD/run.json")"
    if [ "$running" = 0 ]; then
      return 0
    fi
    if [ $(($(date +%s) - start)) -ge "$timeout" ]; then
      fail "run $run_id still has $running RUNNING step rows after ${timeout}s"
    fi
    sleep 1
  done
}

step_field() { # step_field <step-name> <field>  (reads $TMPD/run.json)
  jqr -r --arg s "$1" --arg f "$2" '[.steps[] | select(.stepName == $s)] | if length == 1 then .[0][$f] else "count=\(length)" end' <"$TMPD/run.json"
}

kv() { # kv <file> <key>: value of the first "key=value" line
  awk -v k="$2" 'index($0, k "=") == 1 { print substr($0, length(k) + 2); exit }' "$1"
}

# ---------------------------------------------------------------------------------------------
step "Preflight"
for tool in docker curl openssl; do
  command -v "$tool" >/dev/null 2>&1 || fail "$tool is not installed on the host"
done
docker compose version >/dev/null 2>&1 || fail "docker compose is not available"
[ -f compose.yaml ] || fail "compose.yaml not found in $ROOT_DIR"
[ -f .env ] || fail ".env not found (copy .env.example to .env and fill it in; see docs/blog-agent/LOCAL_DEVELOPMENT.md)"
ok "host tools, compose.yaml and .env present"

step "Build images"
if ! docker compose build >"$TMPD/build.log" 2>&1; then
  tail -n 40 "$TMPD/build.log" | mask
  fail "docker compose build failed"
fi
ok "docker compose build"

step "Check .env values without printing them"
if ! docker compose run --rm --no-deps -T tools sh -c '
  bad=0
  if [ "${#SESSION_SECRET}" -lt 32 ]; then echo "SESSION_SECRET must be at least 32 characters (openssl rand -hex 32)"; bad=1; fi
  case "${POSTGRES_PASSWORD:-}" in
    "" | change-me) echo "POSTGRES_PASSWORD must be set to a generated value (openssl rand -hex 24)"; bad=1 ;;
    *" "*) echo "POSTGRES_PASSWORD must not contain spaces"; bad=1 ;;
  esac
  if [ -z "${BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then
    echo "BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD must be set (the acceptance run checks that admin can sign in)"; bad=1
  fi
  lower() { printf %s "$1" | tr "[:upper:]" "[:lower:]"; }
  case "$(lower "${BLOG_AGENT_MOCK_MODE:-true}")" in
    true | 1 | yes | on) ;;
    *) echo "BLOG_AGENT_MOCK_MODE must be true in Phase 1 (real providers arrive in Phase 2)"; bad=1 ;;
  esac
  case "$(lower "${BLOG_AGENT_ENABLED:-true}")" in
    true | 1 | yes | on) ;;
    *) echo "BLOG_AGENT_ENABLED must be true for the acceptance run"; bad=1 ;;
  esac
  exit "$bad"
' >"$TMPD/envcheck.log" 2>&1; then
  grep -v -E '^ *(Volume|Network|Container) ' "$TMPD/envcheck.log" || true
  fail ".env needs the changes listed above"
fi
ok ".env: SESSION_SECRET length, POSTGRES_PASSWORD, bootstrap admin, mock mode and kill switch"

# ---------------------------------------------------------------------------------------------
step "Start the stack and wait for health"
if ! docker compose up -d --wait --wait-timeout 300 >"$TMPD/up.log" 2>&1; then
  tail -n 20 "$TMPD/up.log" | mask
  docker compose ps -a
  for svc in migrate api worker web; do
    echo "--- last log lines: $svc"
    docker compose logs --no-color --tail 30 "$svc" 2>&1 | mask
  done
  fail "docker compose up -d --wait did not reach a healthy stack"
fi
for svc in db api worker web; do
  health="$(docker compose ps --format '{{.Health}}' "$svc" 2>/dev/null || true)"
  [ "$health" = healthy ] || fail "$svc is '${health:-not running or not defined}', expected healthy"
  ok "$svc is healthy"
done
migrate_state="$(docker compose ps -a --format '{{.State}} {{.ExitCode}}' migrate 2>/dev/null || true)"
[ "$migrate_state" = "exited 0" ] || fail "migrate is '${migrate_state:-not defined}', expected 'exited 0'"
ok "migrate exited 0"
# Fresh api and worker containers: the log checks below then read only this run's logs, not lines left
# over from earlier sessions (for example a shutdown traceback from a `docker compose stop`).
if ! docker compose up -d --no-deps --force-recreate --wait --wait-timeout 300 api worker >"$TMPD/up.log" 2>&1; then
  tail -n 20 "$TMPD/up.log" | mask
  fail "api and worker did not come back healthy after being recreated"
fi
ok "api and worker recreated and healthy (the log checks see only this run)"
API="http://$(docker compose port api 8000)"
WEB="http://$(docker compose port web 5173)"
NETWORK="$(docker inspect -f '{{range $k, $v := .NetworkSettings.Networks}}{{println $k}}{{end}}' "$(docker compose ps -q web)" | head -n 1)"
[ -n "$NETWORK" ] || fail "could not find the compose network of the web container"
info "api $API, web $WEB, network $NETWORK"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' "$API/readyz")"
expect_status "api /readyz" 200 "$code"

# ---------------------------------------------------------------------------------------------
if [ "${SKIP_SUITES:-0}" = 1 ]; then
  step "Test suites skipped (SKIP_SUITES=1)"
  warn "pytest, vitest, lint and build were not run"
else
  step "Backend test suite"
  if docker compose run --rm -T tools pytest -q >"$TMPD/pytest.log" 2>&1; then
    ok "pytest: $(grep -E '[0-9]+ passed' "$TMPD/pytest.log" | tail -n 1)"
  else
    tail -n 60 "$TMPD/pytest.log" | mask
    fail "pytest failed"
  fi

  step "Frontend checks"
  if docker compose run --rm -T -e NO_COLOR=1 web npm test >"$TMPD/vitest.log" 2>&1; then
    ok "vitest: $(strip_ansi <"$TMPD/vitest.log" | grep -E '(Test Files|Tests) +[0-9]+ passed' | tr -s ' ' | paste -s -d ';' -)"
  else
    tail -n 60 "$TMPD/vitest.log"
    fail "npm test failed"
  fi
  if docker compose run --rm -T web npm run lint >"$TMPD/lint.log" 2>&1; then
    ok "npm run lint"
  else
    tail -n 60 "$TMPD/lint.log"
    fail "npm run lint failed"
  fi
  if docker compose run --rm -T web npm run build >"$TMPD/webbuild.log" 2>&1; then
    ok "npm run build (tsc -b && vite build)"
  else
    tail -n 60 "$TMPD/webbuild.log"
    fail "npm run build failed"
  fi
fi

# ---------------------------------------------------------------------------------------------
step "Web dev server serves every nav route and proxies /api"
for path in / /login /ideas /research /drafts /review /published /topics /calendar /sources /settings /agent-runs; do
  code="$(curl -sS -o /dev/null -w '%{http_code}' "$WEB$path")"
  [ "$code" = 200 ] || fail "GET $WEB$path returned HTTP $code"
done
ok "12 routes return the SPA shell (HTTP 200)"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' "$WEB/api/auth/session")"
expect_problem "GET /api/auth/session through the Vite proxy without a cookie" 401 "$code" "Not authenticated"

# ---------------------------------------------------------------------------------------------
step "Accounts via the CLI (passwords generated here, never printed)"
P1_ADMIN_PASSWORD="$(openssl rand -hex 24)"
P1_VIEWER_PASSWORD="$(openssl rand -hex 24)"
export P1_ADMIN_PASSWORD P1_VIEWER_PASSWORD
docker compose exec -T -e P1_ADMIN_PASSWORD api python -m mdcopilot_blog.cli create-admin \
  --email "$P1_ADMIN_EMAIL" --display-name "Acceptance Admin" --password-env P1_ADMIN_PASSWORD >"$TMPD/cli.log" 2>&1 ||
  { mask <"$TMPD/cli.log"; fail "create-admin failed"; }
ok "create-admin $P1_ADMIN_EMAIL"
docker compose exec -T -e P1_VIEWER_PASSWORD api python -m mdcopilot_blog.cli create-user \
  --email "$P1_VIEWER_EMAIL" --display-name "Acceptance Viewer" --role viewer --password-env P1_VIEWER_PASSWORD >"$TMPD/cli.log" 2>&1 ||
  { mask <"$TMPD/cli.log"; fail "create-user failed"; }
ok "create-user $P1_VIEWER_EMAIL (viewer)"

read -r -d '' BOOTSTRAP_LOGIN_PY <<'PY' || true
import json
import os
import urllib.error
import urllib.request

body = json.dumps(
    {"email": os.environ["BOOTSTRAP_ADMIN_EMAIL"], "password": os.environ["BOOTSTRAP_ADMIN_PASSWORD"]}
).encode()
req = urllib.request.Request(
    "http://127.0.0.1:8000/api/auth/login",
    data=body,
    method="POST",
    headers={"Content-Type": "application/json", "Origin": "http://127.0.0.1:8000"},
)
try:
    with urllib.request.urlopen(req) as resp:
        print(resp.status)
except urllib.error.HTTPError as exc:
    print(exc.code)
PY
set +e
docker compose exec -T api sh -c '
  if [ -z "${BOOTSTRAP_ADMIN_EMAIL:-}" ] || [ -z "${BOOTSTRAP_ADMIN_PASSWORD:-}" ]; then exit 3; fi
  python -m mdcopilot_blog.cli create-admin --email "$BOOTSTRAP_ADMIN_EMAIL" --display-name Owner
' >"$TMPD/cli.log" 2>&1
boot_status=$?
set -e
case "$boot_status" in
  0)
    ok "bootstrap admin from .env exists (create-admin is idempotent)"
    boot_code="$(docker compose exec -T api python -c "$BOOTSTRAP_LOGIN_PY" 2>/dev/null | tail -n 1)"
    [ "$boot_code" = 200 ] || fail "bootstrap admin login returned HTTP $boot_code (the account exists, but BOOTSTRAP_ADMIN_PASSWORD does not match it)"
    ok "bootstrap admin can log in (HTTP 200; credentials stayed inside the api container)"
    ;;
  3) fail "acceptance requires BOOTSTRAP_ADMIN_EMAIL and BOOTSTRAP_ADMIN_PASSWORD in .env (see LOCAL_DEVELOPMENT.md section 2)" ;;
  2)
    mask <"$TMPD/cli.log"
    fail "create-admin refused BOOTSTRAP_ADMIN_EMAIL/BOOTSTRAP_ADMIN_PASSWORD (reason above: empty password or email without @)"
    ;;
  *)
    mask <"$TMPD/cli.log"
    fail "create-admin for the bootstrap admin failed (exit $boot_status)"
    ;;
esac

# ---------------------------------------------------------------------------------------------
step "Login with curl cookie jars"
login admin "$P1_ADMIN_EMAIL" P1_ADMIN_PASSWORD
login viewer "$P1_VIEWER_EMAIL" P1_VIEWER_PASSWORD
code="$(api_call viewer GET /api/auth/session)"
expect_status "GET /api/auth/session as viewer" 200 "$code"
[ "$(jqr -r '.user.permissions | join(",")' <"$TMPD/body")" = "blog.view" ] || fail "viewer permissions are not exactly [blog.view]"
ok "viewer permissions are exactly [blog.view]"
code="$(api_call admin GET /api/blog-agent/settings)"
expect_status "GET /api/blog-agent/settings as admin" 200 "$code" --quiet
[ "$(jqr -r '.mockMode' <"$TMPD/body")" = true ] || fail "settings report mockMode=false; Phase 1 needs mock mode"
[ "$(jqr -r '.humanApprovalRequired' <"$TMPD/body")" = true ] || fail "settings report humanApprovalRequired=false"
ok "settings: mockMode=true, humanApprovalRequired=true"
info "settings: agentEnabled=$(jqr -r '.agentEnabled' <"$TMPD/body") schedulerEnabled=$(jqr -r '.schedulerEnabled' <"$TMPD/body") publishingEnabled=$(jqr -r '.publishingEnabled' <"$TMPD/body")"

# ---------------------------------------------------------------------------------------------
step "RBAC"
code="$(api_call viewer GET '/api/blog-agent/runs?limit=5')"
expect_status "viewer GET /api/blog-agent/runs" 200 "$code"
code="$(api_call viewer POST /api/blog-agent/runs '{}')"
expect_problem "viewer POST /api/blog-agent/runs" 403 "$code" "Forbidden"
code="$(api_call viewer GET /api/blog-agent/settings)"
expect_problem "viewer GET /api/blog-agent/settings" 403 "$code" "Forbidden"
code="$(api_call viewer GET /api/admin/users)"
expect_problem "viewer GET /api/admin/users" 403 "$code" "Forbidden"

# ---------------------------------------------------------------------------------------------
step "Admin run: enqueue and complete"
RUN1="$(create_run admin)"
expect_status "admin POST /api/blog-agent/runs" 202 "$(cat "$TMPD/create.status")"
require_uuid "run id" "$RUN1"
wait_for_run admin "$RUN1" 120
wait_for_steps_settled admin "$RUN1" 60
ok "run $RUN1 reached SUCCEEDED"
steps_seen="$(jqr -r '[.steps[] | "\(.stepName):\(.status):\(.tries)"] | sort | join(" ")' <"$TMPD/run.json")"
[ "$steps_seen" = "hello.echo:SUCCEEDED:1 hello.finish:SUCCEEDED:1 hello.open_attempt:SUCCEEDED:1" ] ||
  fail "unexpected steps for $RUN1: $steps_seen"
ok "3 steps, each SUCCEEDED once ($steps_seen)"
calls="$(sql "select count(*) from app.blog_llm_calls where run_id = '$RUN1'")"
[ "$calls" = 1 ] || fail "run $RUN1 has $calls blog_llm_calls rows, expected 1"
ok "run $RUN1 has exactly 1 blog_llm_calls row"
TRACE1="$(jqr -r '.traceId' <"$TMPD/run.json")"
docker compose logs --no-color worker >"$TMPD/worker.log" 2>&1 || true
ctx_lines="$(grep -F "\"run_id\": \"$RUN1\"" "$TMPD/worker.log" | grep -cF "\"trace_id\": \"$TRACE1\"" || true)"
[ "$ctx_lines" -ge 1 ] || fail "worker JSON logs have no line carrying run_id=$RUN1 and its trace_id"
ok "worker JSON logs carry run_id and trace_id for run $RUN1 ($ctx_lines lines)"

# ---------------------------------------------------------------------------------------------
step "CSRF"
code="$(curl -sS -o "$TMPD/body" -w '%{http_code}' -b "$TMPD/admin.jar" -X POST -H "@$TMPD/admin.csrf" \
  -H 'Content-Type: application/json' --data-binary '{}' "$API/api/blog-agent/runs")"
expect_problem "direct POST without an Origin header" 403 "$code" "Origin not allowed"

read -r -d '' PROBE <<'SH' || true
set -eu
base=http://web:5173
printf '{"email":"%s","password":"%s"}' "$P1_ADMIN_EMAIL" "$P1_ADMIN_PASSWORD" >/tmp/login.json
code=$(curl -sS -D /tmp/login.h -o /tmp/login.b -w '%{http_code}' -H 'Origin: http://web:5173' \
  -H "X-Forwarded-For: $SPOOF_IP" -H 'Content-Type: application/json' --data-binary @/tmp/login.json "$base/api/auth/login")
rm -f /tmp/login.json
echo "login=$code"
# curl drops jar cookies for dotless hosts such as "web", so the cookie is copied from Set-Cookie.
cookie=$(sed -n 's/^[Ss]et-[Cc]ookie: *\([^;]*\).*/\1/p' /tmp/login.h | head -n 1)
csrf=$(sed -n 's/.*"csrfToken" *: *"\([^"]*\)".*/\1/p' /tmp/login.b)
title() { sed -n 's/.*"title" *: *"\([^"]*\)".*/\1/p' "$1"; }
post() {
  label=$1
  shift
  code=$(curl -sS -o "/tmp/$label.b" -w '%{http_code}' -X POST -H "Cookie: $cookie" \
    -H 'Content-Type: application/json' --data-binary '{}' "$@" "$base/api/blog-agent/runs")
  echo "$label=$code|$(title "/tmp/$label.b")"
}
post foreign_origin -H 'Origin: http://evil.example' -H "X-CSRF-Token: $csrf"
post cross_site -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: cross-site' -H "X-CSRF-Token: $csrf"
post missing_token -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin'
post wrong_token -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin' -H 'X-CSRF-Token: 00'
post same_origin -H 'Origin: http://web:5173' -H 'Sec-Fetch-Site: same-origin' -H "X-CSRF-Token: $csrf"
echo "run_id=$(sed -n 's/.*"id" *: *"\([0-9a-f-]*\)".*/\1/p' /tmp/same_origin.b | head -n 1)"
code=$(curl -sS -o /dev/null -w '%{http_code}' -X POST -H "Cookie: $cookie" -H 'Origin: http://web:5173' \
  -H 'Sec-Fetch-Site: same-origin' -H "X-CSRF-Token: $csrf" "$base/api/auth/logout")
echo "logout=$code"
SH
docker run --rm --network "$NETWORK" -e P1_ADMIN_EMAIL -e P1_ADMIN_PASSWORD -e SPOOF_IP="$SPOOF_IP" \
  --entrypoint sh "$CURL_IMAGE" -c "$PROBE" >"$TMPD/probe.out" 2>&1 ||
  { mask <"$TMPD/probe.out"; fail "CSRF probe container failed"; }
probe() { kv "$TMPD/probe.out" "$1"; }
[ "$(probe login)" = 200 ] || fail "login through the Vite proxy returned $(probe login)"
ok "login through http://web:5173 (HTTP 200)"
[ "$(probe foreign_origin)" = "403|Origin not allowed" ] || fail "foreign Origin through the proxy: $(probe foreign_origin)"
ok "foreign Origin through the proxy is rejected (403 Origin not allowed)"
[ "$(probe cross_site)" = "403|Cross-site request blocked" ] || fail "Sec-Fetch-Site cross-site: $(probe cross_site)"
ok "Sec-Fetch-Site: cross-site is rejected (403 Cross-site request blocked)"
[ "$(probe missing_token)" = "403|CSRF token missing or invalid" ] || fail "missing token: $(probe missing_token)"
ok "missing X-CSRF-Token is rejected (403)"
[ "$(probe wrong_token)" = "403|CSRF token missing or invalid" ] || fail "wrong token: $(probe wrong_token)"
ok "wrong X-CSRF-Token is rejected (403)"
case "$(probe same_origin)" in
  "202|"*) ok "same-origin POST with the token through http://web:5173 is accepted (202)" ;;
  *) fail "same-origin POST through the proxy: $(probe same_origin)" ;;
esac
[ "$(probe logout)" = 204 ] || fail "logout through the proxy returned $(probe logout)"
ok "logout through the proxy (204)"
RUN2="$(probe run_id)"
require_uuid "proxy run id" "$RUN2"
wait_for_run admin "$RUN2" 120
wait_for_steps_settled admin "$RUN2" 60
ok "run $RUN2 (created through the proxy) reached SUCCEEDED"
# Three logins so far (admin and viewer direct, admin through the proxy), each with a forged X-Forwarded-For.
attempt_ips="$(sql "select count(*) filter (where ip = '$SPOOF_IP'), count(*) filter (where coalesce(ip, '') = ''), count(*)
  from app.login_attempts where email in ('$P1_ADMIN_EMAIL', '$P1_VIEWER_EMAIL')")"
[ "$attempt_ips" = "0|0|3" ] ||
  fail "login_attempts (forged ip|empty ip|total) = $attempt_ips, expected 0|0|3; the api must record the TCP peer, not X-Forwarded-For"
ok "a forged X-Forwarded-For is ignored: login_attempts record the TCP peer for all 3 logins"

# ---------------------------------------------------------------------------------------------
step "Browser check (Chromium in a container on the compose network)"
read -r -d '' BROWSER_JS <<'JS' || true
import { chromium } from 'playwright'

const base = 'http://web:5173'
const pages = [
  ['Dashboard', '/'],
  ["Today's Ideas", '/ideas'],
  ['Research', '/research'],
  ['Drafts', '/drafts'],
  ['Review Queue', '/review'],
  ['Published', '/published'],
  ['Topics', '/topics'],
  ['Content Calendar', '/calendar'],
  ['Sources', '/sources'],
  ['Settings', '/settings'],
  ['Agent Runs', '/agent-runs'],
]
const out = (key, value) => console.log(`${key}=${value}`)
const errors = []
const browser = await chromium.launch()
try {
  const context = await browser.newContext({ viewport: { width: 1280, height: 800 } })
  const page = await context.newPage()
  page.setDefaultTimeout(15000)
  page.on('pageerror', (error) => errors.push(error.message))

  await page.goto(`${base}/login`)
  await page.getByLabel('Email').fill(process.env.P1_ADMIN_EMAIL)
  await page.getByLabel('Password').fill(process.env.P1_ADMIN_PASSWORD)
  await page.getByRole('button', { name: 'Sign in' }).click()
  await page.getByRole('heading', { level: 1, name: 'Dashboard', exact: true }).waitFor()
  out('login', new URL(page.url()).pathname)

  const nav = page.getByRole('navigation', { name: 'Main' })
  out('nav', (await nav.getByRole('link').allInnerTexts()).map((text) => text.trim()).join('|'))
  for (const [label, path] of pages) {
    await nav.getByRole('link', { name: label, exact: true }).click()
    await page.waitForURL(`${base}${path}`)
    try {
      await page.getByRole('heading', { level: 1, name: label, exact: true }).waitFor()
      out(`page:${path}`, label)
    } catch {
      out(`page:${path}`, `missing heading; h1 texts: ${(await page.locator('h1').allInnerTexts()).join(' / ')}`)
    }
  }

  await nav.getByRole('link', { name: 'Dashboard', exact: true }).click()
  const [created] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/blog-agent/runs'),
    page.getByRole('button', { name: "Generate today's blog" }).click(),
  ])
  const run = await created.json()
  out('generate', `${created.status()}|${run.id ?? run.title ?? ''}`)

  await page.getByRole('button', { name: 'Acceptance Admin' }).click()
  const [loggedOut] = await Promise.all([
    page.waitForResponse((r) => r.request().method() === 'POST' && new URL(r.url()).pathname === '/api/auth/logout'),
    page.getByRole('menuitem', { name: 'Sign out' }).click(),
  ])
  await page.waitForURL(`${base}/login`)
  out('logout', loggedOut.status())
  await page.goto(`${base}/agent-runs`)
  await page.getByRole('heading', { level: 1, name: 'Sign in' }).waitFor()
  out('after_logout', new URL(page.url()).pathname)
  out('page_errors', errors.length)
} catch (error) {
  out('error', String(error.message).split('\n').slice(0, 5).join(' | '))
  process.exitCode = 1
} finally {
  await browser.close()
}
JS
printf '%s\n' "$BROWSER_JS" >"$TMPD/browser.mjs"
if ! docker run --rm --network "$NETWORK" -e P1_ADMIN_EMAIL -e P1_ADMIN_PASSWORD -e PLAYWRIGHT_NPM="$PLAYWRIGHT_NPM" \
  -v "$TMPD/browser.mjs:/work/browser.mjs:ro" -w /work "$BROWSER_IMAGE" \
  sh -c 'npm install --no-save --no-audit --no-fund "$PLAYWRIGHT_NPM" >/tmp/npm.log 2>&1 || { tail -n 20 /tmp/npm.log; exit 1; }; node browser.mjs' \
  >"$TMPD/browser.out" 2>&1; then
  mask <"$TMPD/browser.out"
  fail "browser check failed (see the output above)"
fi
browser() { kv "$TMPD/browser.out" "$1"; }
[ "$(browser login)" = / ] || fail "browser sign-in did not reach the Dashboard: $(browser login)"
ok "browser: $P1_ADMIN_EMAIL signs in at http://web:5173/login and lands on Dashboard"
expected_nav="Dashboard|Today's Ideas|Research|Drafts|Review Queue|Published|Topics|Content Calendar|Sources|Settings|Agent Runs"
[ "$(browser nav)" = "$expected_nav" ] || fail "browser sidebar shows: $(browser nav)"
ok "browser: the sidebar lists the 11 nav items in spec order"
for entry in "/:Dashboard" "/ideas:Today's Ideas" "/research:Research" "/drafts:Drafts" "/review:Review Queue" \
  "/published:Published" "/topics:Topics" "/calendar:Content Calendar" "/sources:Sources" "/settings:Settings" \
  "/agent-runs:Agent Runs"; do
  path="${entry%%:*}"
  label="${entry#*:}"
  [ "$(browser "page:$path")" = "$label" ] || fail "browser: $path: $(browser "page:$path")"
  ok "browser: sidebar link \"$label\" opens $path and renders its heading"
done
[ "$(browser page_errors)" = 0 ] || fail "browser: $(browser page_errors) uncaught page errors"
ok "browser: no uncaught JavaScript errors"
generated="$(browser generate)"
case "$generated" in
  "202|"*) ok "browser: \"Generate today's blog\" POST /api/blog-agent/runs passed the CSRF checks (202)" ;;
  *) fail "browser: Generate today's blog returned $generated" ;;
esac
RUN_B="${generated#202|}"
require_uuid "browser run id" "$RUN_B"
if [ "$(browser logout)" != 204 ] || [ "$(browser after_logout)" != /login ]; then
  fail "browser sign-out: logout HTTP $(browser logout), then /agent-runs led to $(browser after_logout)"
fi
ok "browser: Sign out (POST /api/auth/logout 204); /agent-runs then leads to /login"
wait_for_run admin "$RUN_B" 120
wait_for_steps_settled admin "$RUN_B" 60
ok "run $RUN_B (created in the browser) reached SUCCEEDED"

# ---------------------------------------------------------------------------------------------
step "Kill the worker during hello.echo and resume"
snapshot_logs
DELAY_CHANGED=1
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS="$KILL_DELAY_SECONDS" docker compose up -d --no-deps --wait --wait-timeout 120 worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "worker did not come back healthy with the step delay"; }
[ "$(docker compose exec -T worker printenv BLOG_AGENT_MOCK_STEP_DELAY_SECONDS)" = "$KILL_DELAY_SECONDS" ] ||
  fail "worker did not pick up BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=$KILL_DELAY_SECONDS"
ok "worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=$KILL_DELAY_SECONDS"
RUN3="$(create_run admin)"
expect_status "admin POST /api/blog-agent/runs" 202 "$(cat "$TMPD/create.status")"
require_uuid "run id" "$RUN3"
wait_for_step_running admin "$RUN3" hello.echo 120
ok "hello.echo is RUNNING for run $RUN3"
# echo_step sleeps (the mock delay) before its gateway call; 2 s puts the kill inside that sleep,
# so the interrupted execution has not called the gateway yet.
sleep 2
docker compose kill worker >/dev/null 2>&1
killed_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
ok "docker compose kill worker ($killed_at)"
sleep 2
code="$(api_call admin GET "/api/blog-agent/runs/$RUN3")"
[ "$code" = 200 ] || fail "GET run $RUN3 returned HTTP $code while the worker was down"
cp "$TMPD/body" "$TMPD/run.json"
mid_status="$(jqr -r '.status' <"$TMPD/run.json")"
[ "$mid_status" = RESEARCHING ] || fail "run $RUN3 is $mid_status right after the kill, expected RESEARCHING (killed before the gateway call)"
[ "$(step_field hello.echo status)" = RUNNING ] || fail "hello.echo is not RUNNING after the kill: $(step_field hello.echo status)"
mid_calls="$(sql "select count(*) from app.blog_llm_calls where run_id = '$RUN3'")"
[ "$mid_calls" = 0 ] || fail "run $RUN3 already has $mid_calls blog_llm_calls rows at the kill; the kill must land before the gateway call"
ok "while the worker is down: run RESEARCHING, hello.echo still RUNNING, no gateway call recorded yet"
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS="$KILL_DELAY_SECONDS" docker compose up -d --no-deps worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "could not start the worker again"; }
ok "worker started again (same container, same executor id and APP_VERSION)"
wait_for_run admin "$RUN3" 240
wait_for_steps_settled admin "$RUN3" $((KILL_DELAY_SECONDS + 60))
ok "run $RUN3 resumed and reached SUCCEEDED"
info "steps: $(jqr -r '[.steps[] | "\(.stepName) \(.status) tries=\(.tries)"] | join(", ")' <"$TMPD/run.json")"
[ "$(jqr -r '.steps | length' <"$TMPD/run.json")" = 3 ] || fail "run $RUN3 has $(jqr -r '.steps | length' <"$TMPD/run.json") step rows, expected 3"
[ "$(jqr -r '.attempts | length' <"$TMPD/run.json")" = 1 ] || fail "run $RUN3 has more than one attempt; recovery should reuse the workflow"
[ "$(jqr -r '[.steps[] | select(.status != "SUCCEEDED")] | length' <"$TMPD/run.json")" = 0 ] || fail "run $RUN3 has steps that did not succeed"
[ "$(step_field hello.open_attempt tries)" = 1 ] || fail "hello.open_attempt ran again after recovery (tries=$(step_field hello.open_attempt tries))"
[ "$(step_field hello.finish tries)" = 1 ] || fail "hello.finish ran more than once (tries=$(step_field hello.finish tries))"
ok "completed steps were not repeated: hello.open_attempt tries=1, hello.finish tries=1"
echo_tries="$(step_field hello.echo tries)"
[ "$echo_tries" = 2 ] || fail "hello.echo tries=$echo_tries, expected 2 (the interrupted execution plus the resumed one)"
ok "only the interrupted step re-ran: hello.echo tries=2"
# The interrupted execution was killed before its gateway call, so only the resumed execution
# recorded one. The single row belongs to the hello.echo step row and is ok.
call_stats="$(sql "select count(*), count(*) filter (where a.step_name = 'hello.echo'), count(*) filter (where c.status = 'ok')
  from app.blog_llm_calls c left join app.blog_agent_runs a on a.id = c.agent_run_id where c.run_id = '$RUN3'")"
[ "$call_stats" = "1|1|1" ] ||
  fail "run $RUN3 blog_llm_calls (total|echo|ok) = $call_stats, expected 1|1|1 (one gateway call, no duplicate after resume)"
ok "blog_llm_calls for run $RUN3: 1 row on the hello.echo step, ok (no duplicate call after resume)"
recovery_lines="$(docker compose logs --no-color --since "$killed_at" worker 2>&1 | grep -ci 'recover' || true)"
info "worker log lines mentioning recovery since the kill: $recovery_lines"
snapshot_logs
BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0 docker compose up -d --no-deps --wait --wait-timeout 120 worker >"$TMPD/up.log" 2>&1 ||
  { tail -n 20 "$TMPD/up.log" | mask; fail "worker did not come back healthy with the delay restored"; }
[ "$(docker compose exec -T worker printenv BLOG_AGENT_MOCK_STEP_DELAY_SECONDS)" = 0 ] || fail "worker delay was not restored to 0"
DELAY_CHANGED=0
ok "worker recreated with BLOG_AGENT_MOCK_STEP_DELAY_SECONDS=0"

# ---------------------------------------------------------------------------------------------
step "Secrets"
snapshot_logs
sort -u "$TMPD/logs.txt" >"$TMPD/logs.uniq"
log_lines="$(wc -l <"$TMPD/logs.uniq" | tr -d ' ')"

# Hard check (controller ruling A1): the literal value of any configured secret must never appear
# in the api/worker logs. Values are read from the api container's own environment (already loaded
# from .env via env_file, so this script itself never opens or prints .env) and compared with
# `grep -qF --` against the collected log text piped in over stdin; only the *names* of any match
# are reported, never a value.
read -r -d '' SECRET_GREP_SH <<'SH' || true
set -eu
tmp="$(mktemp)"
cat >"$tmp"
bad=""
checked=0
for n in OPENAI_API_KEY GEMINI_API_KEY ANTHROPIC_API_KEY NCBI_API_KEY \
  SESSION_SECRET POSTGRES_PASSWORD BOOTSTRAP_ADMIN_PASSWORD BLOG_PUBLISHER_PASSWORD \
  P1_ADMIN_PASSWORD P1_VIEWER_PASSWORD; do
  eval "val=\${$n:-}"
  # Ruling A1 requires the four provider-key names to fail the run on any non-empty value, with no
  # minimum length. BOOTSTRAP_ADMIN_PASSWORD also has no minimum length any more (owner change 1).
  # Every other value keeps the >=12 gate (short values are noisier to check).
  case "$n" in
    OPENAI_API_KEY | GEMINI_API_KEY | ANTHROPIC_API_KEY | NCBI_API_KEY | BOOTSTRAP_ADMIN_PASSWORD)
      [ -n "$val" ] || continue
      ;;
    *)
      [ "${#val}" -ge 12 ] || continue
      ;;
  esac
  checked=$((checked + 1))
  if grep -qF -- "$val" "$tmp"; then
    bad="$bad $n"
  fi
done
rm -f "$tmp"
if [ -n "$bad" ]; then
  echo "FAIL the values of$bad appear in the logs"
  exit 1
fi
echo "$checked secret values checked"
SH
values_result="$(docker compose exec -T -e P1_ADMIN_PASSWORD -e P1_VIEWER_PASSWORD api sh -c "$SECRET_GREP_SH" <"$TMPD/logs.uniq" 2>&1)" ||
  fail "log secret check: $(printf '%s' "$values_result" | tail -n 1 | mask)"
ok "no configured secret value appears in the api/worker logs ($values_result, $log_lines distinct log lines)"

# Soft check: the spec's literal `grep -E 'sk-|AIza'`. Ordinary text (an asyncio "Task-6" name, for
# example) contains "sk-", so a match here is a WARNING only (controller ruling A1) — the hard check
# above already fails the run on any real configured secret.
leak_lines="$(grep -Ec 'sk-|AIza' "$TMPD/logs.uniq" || true)"
if [ "$leak_lines" = 0 ]; then
  ok "docker compose logs api worker | grep -E 'sk-|AIza' finds nothing ($log_lines distinct log lines checked)"
else
  key_shaped="$(grep -Ec '(^|[^A-Za-z0-9])sk-[A-Za-z0-9_-]{16,}|AIza[0-9A-Za-z_-]{30,}' "$TMPD/logs.uniq" || true)"
  info "grep -E 'sk-|AIza' matched $leak_lines log lines ($key_shaped key-shaped); masked context (at most 10 distinct):"
  { grep -Eo '.{0,20}(sk-|AIza).{0,4}' "$TMPD/logs.uniq" | mask | sort | uniq -c | head -n 10 | sed 's/^/          /'; } || true
  warn "grep -E 'sk-|AIza' matched $leak_lines log lines ($key_shaped key-shaped, none a configured secret per the hard check above); read the masked context before signing off"
fi

read -r -d '' MASK_CHECK_PY <<'PY' || true
import json
import os
import sys

body = sys.stdin.read()
data = json.loads(body)
names = ("OPENAI_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "NCBI_API_KEY")
leaked = [n for n in names if len(os.environ.get(n, "")) >= 12 and os.environ[n] in body]
bad = []
for key, view in sorted(data["providers"].items()):
    preview = view["preview"]
    shaped = preview is None or preview == "set" or (len(preview) == 8 and preview[3] == "…")
    if not shaped or (preview is None) == bool(view["configured"]):
        bad.append(key)
if leaked or bad:
    print(f"FAIL full_keys_in_response={len(leaked)} badly_masked={','.join(bad) or '-'}")
    sys.exit(1)
print("OK " + " ".join(f"{k}={'configured' if v['configured'] else 'unset'}" for k, v in sorted(data["providers"].items())))
PY
code="$(api_call admin GET /api/blog-agent/settings)"
expect_status "GET /api/blog-agent/settings as admin" 200 "$code" --quiet
mask_result="$(docker compose exec -T api python -c "$MASK_CHECK_PY" <"$TMPD/body" 2>&1)" ||
  fail "settings masking check: $(printf '%s' "$mask_result" | tail -n 1 | mask)"
ok "settings return provider keys masked ($mask_result)"

# ---------------------------------------------------------------------------------------------
step "Runtime invariants"
api_launch_lines="$(grep -F 'DBOS launched' "$TMPD/logs.uniq" | grep -c '^api-' || true)"
if [ "$api_launch_lines" != 0 ]; then
  fail "the api process logged 'DBOS launched'; only the worker may call DBOS.launch()"
fi
ok "api never logged 'DBOS launched' (the worker is the only DBOS executor)"
schedule_status="$(sql "select status from dbos.workflow_schedules where schedule_name = 'daily_generation'")"
scheduler_flag="$(docker compose exec -T worker sh -c 'printf %s "${BLOG_AGENT_SCHEDULER_ENABLED:-false}"' | tr '[:upper:]' '[:lower:]')"
case "$scheduler_flag" in
  true | 1 | yes | on) expected_schedule=ACTIVE ;;
  *) expected_schedule=PAUSED ;;
esac
[ "$schedule_status" = "$expected_schedule" ] ||
  fail "daily_generation schedule is '${schedule_status:-missing}', expected $expected_schedule (BLOG_AGENT_SCHEDULER_ENABLED=$scheduler_flag)"
ok "daily_generation schedule is $schedule_status (BLOG_AGENT_SCHEDULER_ENABLED=$scheduler_flag)"

# ---------------------------------------------------------------------------------------------
step "Sign out and close the throwaway accounts"
viewer_id="$(cat "$TMPD/viewer.id")"
require_uuid "viewer id" "$viewer_id"
code="$(api_call admin PATCH "/api/admin/users/$viewer_id" '{"isActive": false}')"
expect_status "admin PATCH /api/admin/users/{viewer} isActive=false" 200 "$code"
code="$(api_call viewer GET /api/auth/session)"
expect_status "deactivated viewer's session no longer resolves" 401 "$code"
code="$(api_call admin POST /api/auth/logout)"
expect_status "admin POST /api/auth/logout" 204 "$code"
code="$(api_call admin GET /api/auth/session)"
expect_status "admin session after logout" 401 "$code"
: >"$TMPD/admin.jar"
: >"$TMPD/viewer.jar"

step "Optional owner check"
info "Open http://localhost:${WEB##*:} in your own browser and sign in as BOOTSTRAP_ADMIN_EMAIL (plan Step 17)."
