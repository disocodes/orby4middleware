#!/usr/bin/env bash
set -Eeuo pipefail
trap 'echo "ERROR setup failed at line $LINENO while running: $BASH_COMMAND" >&2' ERR

DRY_RUN=0
RECONCILE=0
PROFILES=()
SKIP_SERVICES=()

usage() {
  cat <<'EOF'
Usage: ./scripts/setup.sh [options]
  --profile NAME          Enable a Compose profile (repeatable: imaging, fhir)
  --skip-service NAME     Reuse an externally managed service instead of creating it
  --dry-run               Print CREATE/START/SKIP/RECONCILE decisions only
  --reconcile             Explicitly apply changed Compose definitions to existing services
  -h, --help              Show this help

Normal setup is idempotent: running resources are skipped, stopped resources are started,
and only missing resources are created. Real command failures are not suppressed.
EOF
}

while (($#)); do
  case "$1" in
    --profile) PROFILES+=("${2:?profile name required}"); shift 2 ;;
    --skip-service) SKIP_SERVICES+=("${2:?service name required}"); shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --reconcile) RECONCILE=1; shift ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $1" >&2; usage; exit 2 ;;
  esac
done

command -v docker >/dev/null || { echo "ERROR docker is not installed or not on PATH" >&2; exit 1; }
docker compose version >/dev/null

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  if [[ -f .env.example ]]; then
    if ((DRY_RUN)); then echo "CREATE .env from .env.example"; else cp .env.example .env; echo "CREATE .env from .env.example"; fi
  else
    echo "ERROR .env and .env.example are both missing" >&2; exit 1
  fi
else
  echo "SKIP   .env exists"
fi

COMPOSE=(docker compose)
for p in "${PROFILES[@]}"; do COMPOSE+=(--profile "$p"); done

contains() { local needle="$1"; shift; local x; for x in "$@"; do [[ "$x" == "$needle" ]] && return 0; done; return 1; }
run() { if ((DRY_RUN)); then printf 'DRYRUN '; printf '%q ' "$@"; printf '\n'; else "$@"; fi; }

mapfile -t DESIRED < <("${COMPOSE[@]}" config --services)
mapfile -t EXISTING < <("${COMPOSE[@]}" ps -a --services 2>/dev/null || true)
mapfile -t RUNNING < <("${COMPOSE[@]}" ps --services --status running 2>/dev/null || true)

ORDER=(postgres orby orthanc hapi-fhir)
for service in "${DESIRED[@]}"; do contains "$service" "${ORDER[@]}" || ORDER+=("$service"); done

wait_for_postgres() {
  contains postgres "${SKIP_SERVICES[@]}" && return 0
  ((DRY_RUN)) && { echo "CHECK  postgres readiness before starting orby"; return 0; }
  local i
  for i in {1..40}; do
    if "${COMPOSE[@]}" exec -T postgres pg_isready -U orby -d orby >/dev/null 2>&1; then return 0; fi
    sleep 2
  done
  echo "ERROR postgres did not become ready; inspect: docker compose logs postgres" >&2
  return 1
}

for service in "${ORDER[@]}"; do
  contains "$service" "${DESIRED[@]}" || continue
  if contains "$service" "${SKIP_SERVICES[@]}"; then
    echo "SKIP   $service (externally managed; ensure Orby connection settings point to it)"
    continue
  fi

  if [[ "$service" == "orby" ]]; then wait_for_postgres; fi

  if ((RECONCILE)); then
    echo "RECONCILE $service"
    run "${COMPOSE[@]}" up -d --no-deps "$service"
  elif contains "$service" "${RUNNING[@]}"; then
    echo "SKIP   $service already running"
  elif contains "$service" "${EXISTING[@]}"; then
    echo "START  existing $service"
    run "${COMPOSE[@]}" start "$service"
  else
    echo "CREATE $service"
    run "${COMPOSE[@]}" up -d --no-deps "$service"
  fi
done

if ((DRY_RUN)); then
  echo "Dry run complete; no resources were changed."
else
  echo "orby4middleware setup complete."
  "${COMPOSE[@]}" ps
fi
