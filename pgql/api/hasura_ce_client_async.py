# pgql/api/hasura_ce_client_async.py

import logging
from typing import Dict, Optional
import httpx

from pgql.utils.cache import cached
from pgql.utils.config_utils import TimeoutConfig

logger = logging.getLogger("hasura_ce_client")


class HasuraCEClientAsync:
    """Async Hasura CE v2 client with caching and connection pooling."""

    def __init__(self, graphql_endpoint: str, admin_secret: Optional[str] = None):
        self.graphql_endpoint = graphql_endpoint.rstrip("/")
        self.metadata_endpoint = self.graphql_endpoint.rsplit("/v1/graphql", 1)[0] + "/v1/metadata"
        self.admin_secret = admin_secret
        
        # Create async client with connection pooling
        timeout = httpx.Timeout(
            connect=TimeoutConfig.get_connect_timeout(),
            read=TimeoutConfig.get_request_timeout(),
            write=TimeoutConfig.get_request_timeout(),
            pool=TimeoutConfig.get_pool_timeout()
        )
        
        limits = httpx.Limits(
            max_keepalive_connections=TimeoutConfig.get_max_keepalive_connections(),
            max_connections=TimeoutConfig.get_max_connections()
        )
        
        self.client = httpx.AsyncClient(timeout=timeout, limits=limits)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        await self.client.aclose()

    def _headers(self, role: Optional[str] = None) -> Dict[str, str]:
        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if self.admin_secret:
            headers["x-hasura-admin-secret"] = self.admin_secret
        if role:
            headers["x-hasura-role"] = role
        return headers

    @cached(lambda self: f"metadata:{self.metadata_endpoint}")
    async def export_metadata(self) -> Dict:
        """Export Hasura metadata (cached for 5 minutes)."""
        response = await self.client.post(
            self.metadata_endpoint,
            headers=self._headers(),
            json={"type": "export_metadata", "args": {}},
        )
        response.raise_for_status()
        return response.json()

    async def execute_graphql(
        self, 
        query: str, 
        variables: Optional[Dict] = None, 
        role: Optional[str] = None
    ) -> Dict:
        """Execute GraphQL query."""
        response = await self.client.post(
            self.graphql_endpoint,
            headers=self._headers(role=role),
            json={"query": query, "variables": variables or {}},
        )
        response.raise_for_status()
        return response.json()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()
