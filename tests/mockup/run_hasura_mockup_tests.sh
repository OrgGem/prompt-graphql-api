#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/tests/mockup/docker-compose.hasura.yml"

cleanup() {
  docker compose -f "$COMPOSE_FILE" down -v || true
}

trap cleanup EXIT

docker compose -f "$COMPOSE_FILE" up -d

export HASURA_GRAPHQL_ENDPOINT="http://localhost:18080/v1/graphql"
export HASURA_GRAPHQL_ADMIN_SECRET="testsecret"

python -m unittest tests.test_hasura_ce_container_mockup -v
