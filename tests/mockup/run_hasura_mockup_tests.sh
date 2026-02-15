#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/tests/mockup/docker-compose.hasura.yml"
ENV_FILE="$ROOT_DIR/tests/mockup/.env"

compose_cmd() {
  if [[ -f "$ENV_FILE" ]]; then
    docker compose --env-file "$ENV_FILE" -f "$COMPOSE_FILE" "$@"
  else
    docker compose -f "$COMPOSE_FILE" "$@"
  fi
}

cleanup() {
  compose_cmd down -v || true
}

trap cleanup EXIT

compose_cmd up -d

HASURA_PORT="${HASURA_PORT:-18080}"
HASURA_GRAPHQL_ADMIN_SECRET="${HASURA_GRAPHQL_ADMIN_SECRET:-testsecret}"

export HASURA_GRAPHQL_ENDPOINT="http://localhost:${HASURA_PORT}/v1/graphql"
export HASURA_GRAPHQL_ADMIN_SECRET

python -m unittest tests.test_hasura_ce_container_mockup -v
