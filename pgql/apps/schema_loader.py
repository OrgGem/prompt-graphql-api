# pgql/apps/schema_loader.py
"""Load tracked table names from Hasura metadata."""

import logging
from typing import Optional

from pgql.api.hasura_ce_client import HasuraCEClient

logger = logging.getLogger("promptql_apps")


def load_hasura_tables(
    graphql_endpoint: str,
    admin_secret: Optional[str] = None,
) -> list[str]:
    """Connect to Hasura, export metadata, and extract tracked table names.

    Args:
        graphql_endpoint: Hasura GraphQL endpoint URL
        admin_secret: Optional Hasura admin secret

    Returns:
        Sorted list of tracked table names
    """
    if not graphql_endpoint:
        raise ValueError("Hasura GraphQL endpoint is required")

    client = HasuraCEClient(
        graphql_endpoint=graphql_endpoint,
        admin_secret=admin_secret,
    )

    try:
        metadata = client.export_metadata()
    except Exception as e:
        logger.error(f"Failed to export Hasura metadata: {e}")
        raise ValueError(f"Cannot connect to Hasura: {e}")

    tables: list[str] = []
    for source in metadata.get("sources", []):
        source_name = source.get("name", "default")
        for table_info in source.get("tables", []):
            table = table_info.get("table", {})
            if isinstance(table, dict):
                schema = table.get("schema", "public")
                name = table.get("name")
            else:
                schema = "public"
                name = str(table)
            if name:
                # Include schema prefix if not 'public'
                full_name = f"{schema}.{name}" if schema != "public" else name
                tables.append(full_name)

    tables.sort()
    logger.info(f"Loaded {len(tables)} tracked tables from Hasura ({graphql_endpoint})")
    return tables
