#!/usr/bin/env bash
#
# Kirana-IQ — start the stack locally.
#
#   ./start.sh                 Docker: database, API and dashboard
#   ./start.sh --local         Only Postgres in Docker; API and UI on the host
#   ./start.sh --prod          Production images (no source mounts, no reload)
#   ./start.sh --reset         Wipe the database and reseed from scratch
#   ./start.sh --help          Full option list
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# ---------------------------------------------------------------- appearance
if [[ -t 1 ]] && [[ "${NO_COLOR:-}" == "" ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; NC=$'\033[0m'
  BLUE=$'\033[34m'; GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'
else
  BOLD=""; DIM=""; NC=""; BLUE=""; GREEN=""; YELLOW=""; RED=""
fi

STEP=0
step()  { STEP=$((STEP + 1)); printf "\n${BLUE}${BOLD}[%d/%d]${NC} ${BOLD}%s${NC}\n" "$STEP" "$TOTAL_STEPS" "$1"; }
ok()    { printf "      ${GREEN}✓${NC} %s\n" "$1"; }
info()  { printf "      ${DIM}%s${NC}\n" "$1"; }
warn()  { printf "      ${YELLOW}!${NC} %s\n" "$1"; }
die()   { printf "\n${RED}${BOLD}✗ %s${NC}\n\n" "$1" >&2; exit 1; }

usage() {
  cat <<EOF
${BOLD}Kirana-IQ — start${NC}

  ${BOLD}Usage${NC}
    ./start.sh [options]

  ${BOLD}Modes${NC}
    ${BOLD}(default)${NC}      Everything in Docker, with live reload
    --local        Only Postgres in Docker; API and dashboard run on the host
    --prod         Production images: built bundle, no mounts, no reloaders

  ${BOLD}Options${NC}
    --reset        Delete the database volume and reseed from scratch
    --rebuild      Force a rebuild of the Docker images
    --no-train     Skip model training (forecast pages will return 503)
    --no-seed      Skip data generation and loading
    -h, --help     Show this help

  ${BOLD}Examples${NC}
    ./start.sh                    first run: builds, seeds, trains, starts
    ./start.sh --reset            start over with a clean database
    ./start.sh --local            develop the backend with your own venv
EOF
}

# ------------------------------------------------------------------- options
MODE="docker"; RESET=false; REBUILD=false; TRAIN=true; SEED=true

while [[ $# -gt 0 ]]; do
  case "$1" in
    --local)     MODE="local" ;;
    --prod)      MODE="prod" ;;
    --reset)     RESET=true ;;
    --rebuild)   REBUILD=true ;;
    --no-train)  TRAIN=false ;;
    --no-seed)   SEED=false ;;
    -h|--help)   usage; exit 0 ;;
    *)           printf "${RED}Unknown option: %s${NC}\n\n" "$1" >&2; usage; exit 2 ;;
  esac
  shift
done

TOTAL_STEPS=6
[[ "$MODE" == "local" ]] && TOTAL_STEPS=7

API_URL="http://localhost:8000"
UI_URL="http://localhost:5173"
RUN_DIR=".run"

COMPOSE=(docker compose)
[[ "$MODE" == "prod" ]] && COMPOSE=(docker compose -f docker-compose.yml -f docker-compose.prod.yml)

printf "\n${BOLD}Kirana-IQ${NC} ${DIM}— AI-powered inventory forecasting${NC}\n"
printf "${DIM}mode: %s${NC}\n" "$MODE"

# ------------------------------------------------------------ 1. preflight
step "Checking prerequisites"

command -v docker >/dev/null 2>&1 || die "Docker is not installed. See https://docs.docker.com/get-docker/"
if ! docker info >/dev/null 2>&1; then
  warn "Docker daemon is not running — trying to start it"
  if [[ "$(uname)" == "Darwin" ]]; then open -a Docker >/dev/null 2>&1 || true; fi
  for _ in $(seq 1 30); do docker info >/dev/null 2>&1 && break; sleep 2; done
  docker info >/dev/null 2>&1 || die "Could not start Docker. Start Docker Desktop and try again."
fi
ok "Docker $(docker version --format '{{.Server.Version}}' 2>/dev/null || echo 'ready')"

if [[ "$MODE" == "local" ]]; then
  command -v python3 >/dev/null 2>&1 || die "python3 is required for --local mode"
  command -v npm >/dev/null 2>&1 || die "Node.js and npm are required for --local mode"
  ok "python $(python3 --version 2>&1 | cut -d' ' -f2), node $(node --version)"
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  ok "created .env from .env.example"
else
  ok ".env present"
fi

# ------------------------------------------------------------- 2. database
step "Starting PostgreSQL"

if [[ "$RESET" == true ]]; then
  warn "--reset: deleting the database volume"
  "${COMPOSE[@]}" down -v >/dev/null 2>&1 || true
fi

"${COMPOSE[@]}" up -d db >/dev/null 2>&1
printf "      waiting for the database"
for _ in $(seq 1 60); do
  if "${COMPOSE[@]}" ps db 2>/dev/null | grep -q healthy; then break; fi
  printf "."; sleep 1
done
printf "\n"
"${COMPOSE[@]}" ps db | grep -q healthy || die "Database did not become healthy. Check: docker compose logs db"
ok "PostgreSQL healthy on localhost:5432"

# ------------------------------------------------------------ 3. app start
step "Starting the API and dashboard"

BUILD_FLAG=""
[[ "$REBUILD" == true ]] && BUILD_FLAG="--build"

if [[ "$MODE" == "local" ]]; then
  mkdir -p "$RUN_DIR"

  if [[ ! -d .venv ]]; then
    info "creating .venv (first run only)"
    python3 -m venv .venv
  fi
  info "installing backend dependencies"
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -r backend/requirements.txt
  ok "backend dependencies ready"
else
  # shellcheck disable=SC2086
  "${COMPOSE[@]}" up -d $BUILD_FLAG backend frontend >/dev/null 2>&1
  ok "containers started"
fi

if [[ "$MODE" == "local" ]]; then
  # Background the whole subshell and redirect from here, where the working
  # directory is still the repo root. Redirecting inside the subshell would
  # resolve paths relative to backend/, and leaving stdout attached to this
  # script's pipe would keep it open after the script exits.
  ( cd backend && exec ../.venv/bin/python -m uvicorn app.main:app \
      --host 127.0.0.1 --port 8000 --reload ) > "$RUN_DIR/backend.log" 2>&1 </dev/null &
  echo $! > "$RUN_DIR/backend.pid"
  ok "API starting (pid $(cat "$RUN_DIR/backend.pid"), logs: $RUN_DIR/backend.log)"
fi

printf "      waiting for the API"
for _ in $(seq 1 60); do
  curl -sf "$API_URL/health" >/dev/null 2>&1 && break
  printf "."; sleep 1
done
printf "\n"
curl -sf "$API_URL/health" >/dev/null 2>&1 || die "API did not come up. Check logs: ${COMPOSE[*]} logs backend"
ok "API responding at $API_URL"

# ------------------------------------------------------------- 4. seeding
step "Seeding the database"

run_py() {
  # Runs a script from scripts/ either in the container (mounted at /scripts)
  # or in the local venv. Takes the bare filename plus any arguments.
  local script="$1"; shift
  if [[ "$MODE" == "local" ]]; then
    ./.venv/bin/python "scripts/$script" "$@"
  else
    "${COMPOSE[@]}" exec -T -e PYTHONPATH=/app backend python "/scripts/$script" "$@"
  fi
}

if [[ "$SEED" == false ]]; then
  warn "--no-seed: skipping"
else
  # The catalogue endpoint needs a signed-in user now, so the "is it already
  # seeded?" question is asked of the seed script itself: it exits non-zero
  # with an explanation when the demo store already holds data.
  if [[ ! -f data/products.csv ]]; then
    info "generating the synthetic dataset"
    run_py generate_data.py >/dev/null
  fi

  if run_py seed_demo.py >/dev/null 2>&1; then
    ok "demo store seeded: 30 products, ~11k sale lines"
  else
    ok "demo store already seeded"
  fi
fi

# ------------------------------------------------------------ 5. training
step "Preparing the forecasting model"

# The model file is the source of truth here; /model needs authentication.
if [[ "$TRAIN" == false ]]; then
  warn "--no-train: skipping (forecast pages will show an untrained model)"
elif [[ -f models/demand_model.joblib ]]; then
  ok "model already trained"
else
  info "training on the demo store (takes a few seconds)"
  # --shared also writes models/demand_model.joblib, the fallback a brand-new
  # store forecasts with until it has trained a model of its own.
  if [[ "$MODE" == "local" ]]; then
    ( cd backend && ../.venv/bin/python -m app.ml.train_model --store-id 1 --shared 2>&1 \
        | tail -4 | sed 's/^/      /' )
  else
    "${COMPOSE[@]}" exec -T backend python -m app.ml.train_model --store-id 1 --shared 2>&1 \
      | tail -4 | sed 's/^/      /'
  fi
  ok "model trained and saved to models/"
fi

# ------------------------------------------------------------ 6. dashboard
if [[ "$MODE" == "local" ]]; then
  step "Starting the dashboard"
  if [[ ! -d frontend/node_modules ]]; then
    info "installing frontend dependencies (first run only)"
    ( cd frontend && npm install --silent )
  fi
  ( cd frontend && exec npm run dev -- --port 5173 ) > "$RUN_DIR/frontend.log" 2>&1 </dev/null &
  echo $! > "$RUN_DIR/frontend.pid"
  ok "dashboard starting (pid $(cat "$RUN_DIR/frontend.pid"), logs: $RUN_DIR/frontend.log)"
fi

step "Ready"
printf "      waiting for the dashboard"
for _ in $(seq 1 60); do
  curl -sf "$UI_URL" >/dev/null 2>&1 && break
  printf "."; sleep 1
done
printf "\n"
if curl -sf "$UI_URL" >/dev/null 2>&1; then ok "dashboard responding"; else warn "dashboard not responding yet — give it a moment"; fi

# --------------------------------------------------------------- summary
SUMMARY=$(curl -sf "$API_URL/inventory/summary" 2>/dev/null || true)
printf "\n${GREEN}${BOLD}  Kirana-IQ is running${NC}\n\n"
printf "    ${BOLD}Dashboard${NC}   %s\n" "$UI_URL"
printf "    ${BOLD}API${NC}         %s\n" "$API_URL"
printf "    ${BOLD}API docs${NC}    %s/docs\n" "$API_URL"
printf "    ${BOLD}Database${NC}    postgresql://localhost:5432/kirana_iq\n"

if [[ -n "$SUMMARY" ]]; then
  CRIT=$(echo "$SUMMARY" | sed -n 's/.*"critical_products":\([0-9]*\).*/\1/p')
  HIGH=$(echo "$SUMMARY" | sed -n 's/.*"high_risk_products":\([0-9]*\).*/\1/p')
  OVER=$(echo "$SUMMARY" | sed -n 's/.*"overstocked_products":\([0-9]*\).*/\1/p')
  printf "\n    ${DIM}%s critical · %s high risk · %s overstocked${NC}\n" "${CRIT:-?}" "${HIGH:-?}" "${OVER:-?}"
fi

printf "\n  ${BOLD}Next${NC}\n"
if [[ "$MODE" == "local" ]]; then
  printf "    tail -f %s/backend.log     follow API logs\n" "$RUN_DIR"
else
  printf "    docker compose logs -f backend   follow API logs\n"
fi
printf "    ./stop.sh                        stop everything\n"
printf "    ./stop.sh --reset                stop and delete the database\n\n"
