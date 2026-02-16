# pgql/api/schema_extractor.py
"""Extract compact schema DSL from Hasura CE via GraphQL introspection.

Produces an LLM-friendly text representation of the database schema
including table columns, types, aggregate capabilities, and detected
foreign-key relationships.
"""

import logging
import re
from typing import Dict, List, Optional, Tuple

from pgql.utils.cache import cached

logger = logging.getLogger("schema_extractor")

# Pattern for detecting FK columns: ends with _id
_FK_PATTERN = re.compile(r'^(.+)_id$')


def extract_schema(
    hasura_client,
    allowed_tables: Optional[List[str]] = None,
    include_aggregates: bool = True,
) -> str:
    """Extract compact schema DSL from Hasura CE.

    Returns a multi-line text suitable for LLM system prompts:
        ## Database Schema
        users: id(Int!), name(String!), email(String!)
        users_aggregate: count, sum(id), avg(id)
        products: id(Int!), name(String!), price(numeric!), user_id(Int!) → users
        ...

    Args:
        hasura_client: HasuraCEClient instance
        allowed_tables: If set, only include these tables
        include_aggregates: Whether to include _aggregate type info
    """
    # Step 1: Get list of available root fields from query_root
    root_fields = _get_root_fields(hasura_client)
    if not root_fields:
        return "No tables found in database schema."

    # Step 2: Filter to actual data tables (exclude aggregates, _by_pk, etc.)
    table_names = _filter_table_names(root_fields, allowed_tables)
    if not table_names:
        return "No accessible tables found."

    # Step 3: Detect relationships from FK column patterns
    all_table_info = {}
    for table_name in table_names:
        info = _introspect_table(hasura_client, table_name)
        if info:
            all_table_info[table_name] = info

    relationships = _detect_relationships(all_table_info, table_names)

    # Step 4: Build compact DSL
    lines = ["## Database Schema", ""]

    for table_name in sorted(all_table_info.keys()):
        info = all_table_info[table_name]
        columns = info["columns"]

        # Build column descriptors with FK annotations
        col_parts = []
        for col in columns:
            col_str = f"{col['name']}({col['type']})"
            # Annotate FK relationships
            fk_target = relationships.get(f"{table_name}.{col['name']}")
            if fk_target:
                col_str += f" → {fk_target}"
            col_parts.append(col_str)

        lines.append(f"{table_name}: {', '.join(col_parts)}")

        # Add aggregate info if available
        if include_aggregates and info.get("has_aggregate"):
            numeric_cols = [c["name"] for c in columns if c["is_numeric"]]
            agg_parts = ["count"]
            if numeric_cols:
                for fn in ["sum", "avg", "max", "min"]:
                    agg_parts.append(f"{fn}({','.join(numeric_cols)})")
            lines.append(f"{table_name}_aggregate: {', '.join(agg_parts)}")

        lines.append("")

    # Step 5: Add relationship summary
    if relationships:
        lines.append("## Relationships")
        fk_summary = {}
        for fk_col, target_table in relationships.items():
            src_table = fk_col.split(".")[0]
            fk_summary.setdefault(src_table, []).append(f"{fk_col.split('.')[1]} → {target_table}")
        for src, rels in sorted(fk_summary.items()):
            lines.append(f"{src}: {', '.join(rels)}")
        lines.append("")

    # Step 6: Add Hasura-specific query hints
    lines.extend([
        "## Query Capabilities",
        "- Filtering: where: {field: {_eq/_gt/_lt/_like/_in: value}}",
        "- Sorting: order_by: {field: asc/desc}",
        "- Pagination: limit: N, offset: N",
        "- Aggregation: TABLE_aggregate { aggregate { count, sum { field }, avg { field } } }",
        "- Cross-table via FK: TABLE(order_by: {RELATED_aggregate: {count: desc}})",
    ])

    return "\n".join(lines)


def _get_root_fields(hasura_client) -> List[str]:
    """Get all root query field names from GraphQL introspection."""
    try:
        query = """
        query {
            __schema {
                queryType {
                    fields { name }
                }
            }
        }
        """
        result = hasura_client.execute_graphql(query)
        fields = result.get("data", {}).get("__schema", {}).get("queryType", {}).get("fields", [])
        return [f["name"] for f in fields]
    except Exception as e:
        logger.error(f"Failed to get root fields: {e}")
        return []


def _filter_table_names(root_fields: List[str], allowed_tables: Optional[List[str]]) -> List[str]:
    """Filter root fields to actual data table names.

    Excludes _aggregate, _by_pk, _stream suffixed fields.
    """
    exclude_suffixes = ("_aggregate", "_by_pk", "_stream", "_mutation_response")
    tables = []
    for name in root_fields:
        if any(name.endswith(s) for s in exclude_suffixes):
            continue
        if name.startswith("__"):
            continue
        if allowed_tables is not None and name not in allowed_tables:
            continue
        tables.append(name)
    return sorted(set(tables))


def _introspect_table(hasura_client, table_name: str) -> Optional[Dict]:
    """Introspect a single table type via GraphQL __type.

    Returns:
        {
            "columns": [{"name": "id", "type": "Int!", "is_numeric": True}, ...],
            "has_aggregate": True/False
        }
    """
    try:
        query = """
        query IntrospectType($name: String!) {
            __type(name: $name) {
                fields {
                    name
                    type {
                        name
                        kind
                        ofType { name kind }
                    }
                }
            }
        }
        """
        result = hasura_client.execute_graphql(query, variables={"name": table_name})
        type_info = result.get("data", {}).get("__type")
        if not type_info:
            return None

        columns = []
        has_aggregate = False
        numeric_types = {"Int", "Float", "numeric", "bigint", "smallint", "float8", "float4"}

        for field in type_info.get("fields", []):
            field_name = field["name"]
            field_type = field.get("type", {})
            type_kind = field_type.get("kind", "")
            type_name = field_type.get("name", "")
            inner = field_type.get("ofType") or {}
            inner_name = inner.get("name", "")
            inner_kind = inner.get("kind", "")

            # Skip object/list types (these are relationships, not scalar columns)
            if type_kind in ("OBJECT", "LIST"):
                # Check if this is the _aggregate field
                if field_name == f"{table_name}_aggregate" or field_name.endswith("_aggregate"):
                    has_aggregate = True
                continue
            if type_kind == "NON_NULL" and inner_kind in ("OBJECT", "LIST"):
                continue

            # Build type string
            if type_kind == "NON_NULL":
                resolved_type = f"{inner_name}!"
                is_numeric = inner_name in numeric_types
            elif type_kind == "SCALAR":
                resolved_type = type_name
                is_numeric = type_name in numeric_types
            else:
                resolved_type = type_name or type_kind
                is_numeric = False

            columns.append({
                "name": field_name,
                "type": resolved_type,
                "is_numeric": is_numeric,
            })

        return {
            "columns": columns,
            "has_aggregate": has_aggregate,
        }
    except Exception as e:
        logger.warning(f"Failed to introspect table '{table_name}': {e}")
        return None


def _detect_relationships(
    table_info: Dict[str, Dict],
    table_names: List[str],
) -> Dict[str, str]:
    """Detect FK relationships from column naming conventions.

    Looks for columns ending in '_id' and checks if a matching table exists.
    E.g., products.user_id → users, orders.product_id → products

    Returns:
        {"products.user_id": "users", "orders.user_id": "users", ...}
    """
    relationships = {}
    table_set = set(table_names)

    for table_name, info in table_info.items():
        for col in info.get("columns", []):
            match = _FK_PATTERN.match(col["name"])
            if match:
                potential_table = match.group(1)
                # Try plural forms
                for candidate in [potential_table, f"{potential_table}s", f"{potential_table}es",
                                  potential_table.rstrip("y") + "ies"]:
                    if candidate in table_set and candidate != table_name:
                        relationships[f"{table_name}.{col['name']}"] = candidate
                        break

    return relationships
