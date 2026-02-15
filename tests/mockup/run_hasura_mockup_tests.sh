#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/tests/mockup/docker-compose.hasura.yml"
ENV_FILE="$ROOT_DIR/tests/mockup/.env"
VALIDATION_LOG=""

compose_cmd() {
  local compose_args=()
  if [[ -f "$ENV_FILE" ]]; then
    echo "Using env file: $ENV_FILE"
    compose_args=(--env-file "$ENV_FILE")
  fi
  docker compose "${compose_args[@]}" -f "$COMPOSE_FILE" "$@"
}

cleanup() {
  compose_cmd down -v || true
  if [[ -n "$VALIDATION_LOG" ]]; then
    rm -f "$VALIDATION_LOG" || true
  fi
}

trap cleanup EXIT

umask 077
VALIDATION_LOG="$(mktemp)"
if ! compose_cmd config >"$VALIDATION_LOG" 2>&1; then
  cat "$VALIDATION_LOG" >&2
  if [[ -f "$ENV_FILE" ]]; then
    echo "Invalid docker compose configuration. Check $COMPOSE_FILE and $ENV_FILE syntax." >&2
  else
    echo "Invalid docker compose configuration. Check $COMPOSE_FILE syntax." >&2
  fi
  exit 1
fi

compose_cmd up -d

HASURA_PORT="${HASURA_PORT:-18080}"
HASURA_GRAPHQL_ADMIN_SECRET="${HASURA_GRAPHQL_ADMIN_SECRET:-testsecret}"

export HASURA_GRAPHQL_ENDPOINT="http://localhost:${HASURA_PORT}/v1/graphql"
export HASURA_GRAPHQL_ADMIN_SECRET

python -m unittest tests.test_hasura_ce_container_mockup -v
