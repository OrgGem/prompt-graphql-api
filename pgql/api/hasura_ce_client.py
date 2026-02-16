import logging
import re
from typing import Dict, Optional

import requests

from pgql.utils.cache import cached
from pgql.utils.config_utils import TimeoutConfig

# Whitelist pattern for GraphQL identifiers (table/field names)
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

logger = logging.getLogger("hasura_ce_client")


class HasuraCEClient:
    """Minimal Hasura CE v2 client for metadata + GraphQL execution."""

    def __init__(self, graphql_endpoint: str, admin_secret: Optional[str] = None, timeout: int = 30):
        self.graphql_endpoint = graphql_endpoint.rstrip("/")
        self.metadata_endpoint = self.graphql_endpoint.rsplit("/v1/graphql", 1)[0] + "/v1/metadata"
        self.admin_secret = admin_secret
        self.timeout = timeout or TimeoutConfig.get_request_timeout()

    def _headers(self, role: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.admin_secret:
            headers["x-hasura-admin-secret"] = self.admin_secret
        if role:
            headers["x-hasura-role"] = role
        return headers

    @cached(lambda self: f"hasura_metadata:{self.metadata_endpoint}")
    def export_metadata(self) -> Dict:
        """Export Hasura metadata (cached for 5 minutes)."""
        response = requests.post(
            self.metadata_endpoint,
            headers=self._headers(),
            json={"type": "export_metadata", "args": {}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def execute_graphql(self, query: str, variables: Optional[Dict] = None, role: Optional[str] = None) -> Dict:
        response = requests.post(
            self.graphql_endpoint,
            headers=self._headers(role=role),
            json={"query": query, "variables": variables or {}},
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.json()

    def get_tracked_tables(self, allowed_tables: Optional[list] = None) -> list:
        """Get tracked table names from metadata, optionally filtered by allowed_tables."""
        metadata = self.export_metadata()
        tables = []
        for source in metadata.get("sources", []):
            for table_info in source.get("tables", []):
                table = table_info.get("table", {})
                name = table.get("name") if isinstance(table, dict) else str(table)
                if name:
                    if allowed_tables and name not in allowed_tables:
                        continue
                    tables.append(name)
        return tables

    def query_sample_rows(self, table_name: str, limit: int = 5, role: Optional[str] = None) -> Dict:
        """Query sample rows from a table for LLM context."""
        if not _SAFE_NAME_RE.match(table_name):
            return {"columns": [], "rows": [], "error": f"Invalid table name: '{table_name}'"}
        limit = max(1, min(int(limit), 100))  # Clamp to safe range
        # First get columns via introspection, then query with actual fields
        intro_query = (
            "query IntrospectType($name: String!) {"
            "  __type(name: $name) {"
            "    fields { name type { name kind ofType { name } } }"
            "  }"
            "}"
        )
        try:
            intro_result = self.execute_graphql(intro_query, variables={"name": table_name}, role=role)
            type_info = intro_result.get("data", {}).get("__type")
            if not type_info:
                return {"columns": [], "rows": [], "error": f"Type '{table_name}' not found"}

            # Filter to scalar fields only (skip nested objects/arrays)
            scalar_fields = []
            for field in type_info.get("fields", []):
                fname = field["name"]
                if not _SAFE_NAME_RE.match(fname):
                    continue  # Skip fields with unsafe names
                kind = field["type"].get("kind", "")
                inner_kind = (field["type"].get("ofType") or {}).get("name", "")
                # Include SCALAR and NON_NULL wrapping a scalar
                if kind == "SCALAR" or (kind == "NON_NULL" and inner_kind):
                    scalar_fields.append(fname)

            if not scalar_fields:
                return {"columns": [], "rows": [], "error": "No scalar fields found"}

            # Query with actual scalar fields
            fields_str = " ".join(scalar_fields[:20])  # Cap at 20 columns
            data_query = f"query {{ {table_name}(limit: {limit}) {{ {fields_str} }} }}"
            result = self.execute_graphql(data_query, role=role)
            rows = result.get("data", {}).get(table_name, [])

            return {"columns": scalar_fields[:20], "rows": rows}
        except (requests.RequestException, KeyError, ValueError) as e:
            logger.warning(f"Failed to sample table '{table_name}': {e}")
            return {"columns": [], "rows": [], "error": str(e)}
