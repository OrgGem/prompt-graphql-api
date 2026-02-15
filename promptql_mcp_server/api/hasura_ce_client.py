import logging
from typing import Dict, Optional

import requests

logger = logging.getLogger("hasura_ce_client")


class HasuraCEClient:
    """Minimal Hasura CE v2 client for metadata + GraphQL execution."""

    def __init__(self, graphql_endpoint: str, admin_secret: Optional[str] = None, timeout: int = 30):
        self.graphql_endpoint = graphql_endpoint.rstrip("/")
        self.metadata_endpoint = self.graphql_endpoint.rsplit("/v1/graphql", 1)[0] + "/v1/metadata"
        self.admin_secret = admin_secret
        self.timeout = timeout

    def _headers(self, role: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.admin_secret:
            headers["x-hasura-admin-secret"] = self.admin_secret
        if role:
            headers["x-hasura-role"] = role
        return headers

    def export_metadata(self) -> Dict:
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
