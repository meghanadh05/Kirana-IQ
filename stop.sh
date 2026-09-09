#!/usr/bin/env bash
#
# Kirana-IQ — stop the stack.
#
#   ./stop.sh              Stop containers and any locally started processes
#   ./stop.sh --reset      Also delete the database volume (destroys all data)
#   ./stop.sh --clean      Also remove generated data, models and logs
#   ./stop.sh --help       Full option list
#
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

if [[ -t 1 ]] && [[ "${NO_COLOR:-}" == "" ]]; then
  BOLD=$'\033[1m'; DIM=$'\033[2m'; NC=$'\033[0m'
  GREEN=$'\033[32m'; YELLOW=$'\033[33m'; RED=$'\033[31m'; BLUE=$'\033[34m'
else
  BOLD=""; DIM=""; NC=""; GREEN=""; YELLOW=""; RED=""; BLUE=""
fi

ok()   { printf "      ${GREEN}✓${NC} %s\n" "$1"; }
info() { printf "      ${DIM}%s${NC}\n" "$1"; }
warn() { printf "      ${YELLOW}!${NC} %s\n" "$1"; }
head_() { printf "\n${BLUE}${BOLD}%s${NC}\n" "$1"; }

usage() {
  cat <<EOF
${BOLD}Kirana-IQ — stop${NC}

  ${BOLD}Usage${NC}
    ./stop.sh [options]

  ${BOLD}Options${NC}
    ${BOLD}(none)${NC}         Stop containers and local processes; keep all data
    --reset        Also delete the database volume ${RED}(destroys all data)${NC}
    --clean        Also remove generated CSVs, trained models and logs
    -h, --help     Show this help

  ${BOLD}Examples${NC}
    ./stop.sh                 pause work; everything is kept
    ./stop.sh --reset         start fresh next time
    ./stop.sh --reset --clean remove every generated artefact too
EOF
}

RESET=false; CLEAN=false
while [[ $# -gt 0 ]]; do
  case "$1" in
    --reset)   RESET=true ;;
    --clean)   CLEAN=true ;;
    -h|--help) usage; exit 0 ;;
    *)         printf "${RED}Unknown option: %s${NC}\n\n" "$1" >&2; usage; exit 2 ;;
  esac
  shift
done

RUN_DIR=".run"
printf "\n${BOLD}Kirana-IQ${NC} ${DIM}— shutting down${NC}\n"

# ------------------------------------------------- locally started processes
head_ "Local processes"
STOPPED_ANY=false
for name in backend frontend; do
  PID_FILE="$RUN_DIR/$name.pid"
  if [[ -f "$PID_FILE" ]]; then
    PID=$(cat "$PID_FILE")
    # Kill the whole process group: npm and uvicorn --reload both spawn children.
    if kill -0 "$PID" 2>/dev/null; then
      pkill -P "$PID" 2>/dev/null || true
      kill "$PID" 2>/dev/null || true
      sleep 1
      kill -9 "$PID" 2>/dev/null || true
      ok "stopped $name (pid $PID)"
    else
      info "$name was not running"
    fi
    rm -f "$PID_FILE"
    STOPPED_ANY=true
  fi
done
[[ "$STOPPED_ANY" == false ]] && info "none were started with --local"

# Anything still holding the ports (a stray run from a previous session).
for port in 8000 5173; do
  if lsof -ti:"$port" >/dev/null 2>&1; then
    lsof -ti:"$port" | xargs kill -9 2>/dev/null || true
    ok "freed port $port"
  fi
done

# --------------------------------------------------------------- containers
head_ "Containers"
VOLUME_DELETED=false
if ! docker info >/dev/null 2>&1; then
  warn "Docker is not running — no containers to stop"
else
  if [[ "$RESET" == true ]]; then
    docker compose down -v >/dev/null 2>&1 || true
    VOLUME_DELETED=true
    ok "containers stopped and database volume deleted"
  else
    docker compose down >/dev/null 2>&1 || true
    ok "containers stopped (database volume kept)"
  fi
fi

# ------------------------------------------------------ generated artefacts
if [[ "$CLEAN" == true ]]; then
  head_ "Generated files"
  rm -f data/products.csv data/sales.csv && ok "removed generated CSVs"
  rm -f models/*.joblib models/*.json 2>/dev/null || true
  ok "removed trained models"
  rm -rf "$RUN_DIR" && ok "removed logs"
  info "data/events.csv kept — it is source data, not generated"
fi

printf "\n${GREEN}${BOLD}  Stopped${NC}\n\n"
if [[ "$VOLUME_DELETED" == true ]]; then
  printf "    ${DIM}The database was deleted. ./start.sh will reseed it.${NC}\n\n"
elif [[ "$RESET" == true ]]; then
  # --reset was asked for but Docker was down, so nothing was actually removed.
  printf "    ${YELLOW}--reset had no effect: Docker was not running.${NC}\n"
  printf "    ${DIM}Start Docker and re-run ./stop.sh --reset to delete the database.${NC}\n\n"
else
  printf "    ${DIM}Data was kept. Run ./start.sh to pick up where you left off.${NC}\n\n"
fi
