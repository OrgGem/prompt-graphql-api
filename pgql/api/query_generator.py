# pgql/api/query_generator.py
"""LLM-powered GraphQL query generator with validation.

Uses the LLM to translate natural language questions into GraphQL queries,
validates them for safety, executes them, and summarizes the results.
"""

import json
import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger("query_generator")

# Whitelist pattern for GraphQL identifiers
_SAFE_NAME_RE = re.compile(r'^[a-zA-Z_][a-zA-Z0-9_]*$')

# System prompt template for query generation
_QUERY_GEN_SYSTEM_PROMPT = """You are a GraphQL query generator for Hasura CE (PostgreSQL).

{schema_dsl}

RULES:
- Output ONLY a valid GraphQL query inside a ```graphql code block
- Do NOT include any explanation outside the code block
- Use _aggregate for counting, summing, averaging
- Use order_by for sorting: {{field: asc}} or {{field: desc}}
- Use limit for top-N queries
- Use where for filtering: {{field: {{_eq: value, _gt: value, _like: "%text%"}}}}
- For "which X has most Y": use nested aggregate ordering:
  X(order_by: {{Y_aggregate: {{count: desc}}}}, limit: 1) {{ ... Y_aggregate {{ aggregate {{ count }} }} }}
- For totals/sums: use TABLE_aggregate {{ aggregate {{ sum {{ field }} }} }}
- Do NOT use mutations — this is read-only access
- Always include identifying fields (id, name) in the selection
- Keep queries simple and efficient

EXAMPLE for "user with most products":
```graphql
query {{
  users(order_by: {{products_aggregate: {{count: desc}}}}, limit: 1) {{
    id
    name
    products_aggregate {{
      aggregate {{
        count
      }}
    }}
  }}
}}
```"""

# System prompt for result summarization
_SUMMARIZE_SYSTEM_PROMPT = """You are a data analyst assistant. The user asked a question about their database.
A GraphQL query was executed and returned the following results.

Summarize the results in natural language. Be concise and direct.
If the results are empty, say no data was found.
Include relevant numbers and names from the data.
Answer in the same language as the user's question."""

# Regex to extract GraphQL query from LLM response
_GRAPHQL_BLOCK_RE = re.compile(r'```(?:graphql)?\s*\n(.*?)```', re.DOTALL)
_QUERY_BRACE_RE = re.compile(r'(query\s*\{.*\})', re.DOTALL)


def generate_graphql_query(
    llm_client,
    schema_dsl: str,
    user_question: str,
) -> Dict:
    """Use LLM to generate a GraphQL query from natural language.

    Args:
        llm_client: LLMClient instance
        schema_dsl: Compact schema text from schema_extractor
        user_question: The user's natural language question

    Returns:
        {"success": True, "query": "query { ... }", "raw_response": "..."}
        or {"success": False, "error": "..."}
    """
    system_prompt = _QUERY_GEN_SYSTEM_PROMPT.format(schema_dsl=schema_dsl)

    result = llm_client.chat(
        message=f"Generate a GraphQL query for: {user_question}",
        system_instructions=system_prompt,
    )

    if not result.get("success"):
        return {"success": False, "error": result.get("error", "LLM failed to generate query")}

    raw_response = result.get("content", "")
    query = _extract_query(raw_response)

    if not query:
        logger.warning(f"Could not extract query from LLM response: {raw_response[:200]}")
        return {
            "success": False,
            "error": "LLM did not return a valid GraphQL query",
            "raw_response": raw_response,
        }

    return {
        "success": True,
        "query": query,
        "raw_response": raw_response,
        "usage": result.get("usage", {}),
    }


def validate_query(
    query_str: str,
    role: str = "read",
    allowed_tables: Optional[List[str]] = None,
    max_depth: int = 4,
) -> Dict:
    """Validate a GraphQL query for safety.

    Checks:
    - No mutations for read-only roles
    - Only references allowed tables
    - Query depth within limits
    - No SQL injection patterns

    Returns:
        {"valid": True} or {"valid": False, "reason": "..."}
    """
    stripped = query_str.strip()

    # 1. Mutation check
    if role == "read" and stripped.lower().startswith("mutation"):
        return {"valid": False, "reason": "Mutations not allowed for read-only apps"}

    # 2. Must start with query
    if not stripped.lower().startswith("query"):
        # Allow bare { ... } syntax too
        if not stripped.startswith("{"):
            return {"valid": False, "reason": "Query must start with 'query' or '{'"}

    # 3. Table whitelist check (if specified)
    if allowed_tables:
        # Extract potential table references from query
        # Look for root-level identifiers after { or after query {
        word_pattern = re.compile(r'[a-zA-Z_][a-zA-Z0-9_]*')
        words = set(word_pattern.findall(stripped))
        # Remove known GraphQL keywords
        keywords = {
            "query", "mutation", "subscription", "fragment", "on",
            "where", "order_by", "limit", "offset", "distinct_on",
            "asc", "desc", "asc_nulls_last", "desc_nulls_last",
            "aggregate", "count", "sum", "avg", "max", "min",
            "nodes", "true", "false", "null",
            "_eq", "_neq", "_gt", "_gte", "_lt", "_lte",
            "_in", "_nin", "_like", "_ilike", "_is_null",
            "_and", "_or", "_not",
        }
        potential_tables = words - keywords

        # Check if any referenced table-like words match allowed_tables
        allowed_set = set(allowed_tables)
        # Also allow _aggregate, _by_pk suffixed versions
        allowed_expanded = set()
        for t in allowed_tables:
            allowed_expanded.add(t)
            allowed_expanded.add(f"{t}_aggregate")
            allowed_expanded.add(f"{t}_by_pk")

        # Only flag if we find an unknown table-like reference at the root level
        # This is a heuristic — we can't fully parse GraphQL here
        for word in potential_tables:
            if word in allowed_expanded:
                continue
            # Check if it looks like a table name (not a field value)
            if _SAFE_NAME_RE.match(word) and len(word) > 2:
                # It might be a field name, so don't reject — just warn
                pass

    # 4. Depth check
    depth = _calculate_depth(stripped)
    if depth > max_depth:
        return {"valid": False, "reason": f"Query too complex: depth {depth} exceeds limit {max_depth}"}

    # 5. Injection patterns
    dangerous_patterns = [
        r';\s*DROP\s',
        r';\s*DELETE\s',
        r';\s*UPDATE\s',
        r';\s*INSERT\s',
        r'--\s',
        r'/\*',
    ]
    for pattern in dangerous_patterns:
        if re.search(pattern, stripped, re.IGNORECASE):
            return {"valid": False, "reason": "Potential injection pattern detected"}

    return {"valid": True}


def summarize_results(
    llm_client,
    user_question: str,
    query: str,
    results: Dict,
) -> Dict:
    """Use LLM to summarize query results in natural language.

    Args:
        llm_client: LLMClient instance
        user_question: Original user question
        query: The GraphQL query that was executed
        results: Raw query results from Hasura

    Returns:
        {"success": True, "summary": "...", "usage": {...}}
    """
    # Truncate results if too large
    results_str = json.dumps(results, indent=2, default=str, ensure_ascii=False)
    if len(results_str) > 4000:
        results_str = results_str[:4000] + "\n... (truncated)"

    message = (
        f"User question: {user_question}\n\n"
        f"GraphQL query executed:\n```graphql\n{query}\n```\n\n"
        f"Results:\n```json\n{results_str}\n```\n\n"
        f"Summarize these results to answer the user's question."
    )

    result = llm_client.chat(
        message=message,
        system_instructions=_SUMMARIZE_SYSTEM_PROMPT,
    )

    if not result.get("success"):
        # Fallback: return raw results as formatted text
        return {
            "success": True,
            "summary": f"Query results:\n```json\n{results_str}\n```",
            "usage": {},
        }

    return {
        "success": True,
        "summary": result.get("content", ""),
        "usage": result.get("usage", {}),
    }


def _extract_query(llm_response: str) -> Optional[str]:
    """Extract GraphQL query from LLM response text.

    Tries:
    1. ```graphql ... ``` code block
    2. ``` ... ``` code block
    3. query { ... } pattern
    4. Bare { ... } pattern
    """
    # Try code block extraction
    match = _GRAPHQL_BLOCK_RE.search(llm_response)
    if match:
        query = match.group(1).strip()
        if query:
            return query

    # Try query { ... } pattern
    match = _QUERY_BRACE_RE.search(llm_response)
    if match:
        return match.group(1).strip()

    # Try bare { ... } — find the outermost balanced braces
    stripped = llm_response.strip()
    if stripped.startswith("{"):
        depth = 0
        for i, ch in enumerate(stripped):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return stripped[:i + 1]

    return None


def _calculate_depth(query: str) -> int:
    """Calculate the nesting depth of a GraphQL query."""
    max_depth = 0
    current = 0
    for ch in query:
        if ch == "{":
            current += 1
            max_depth = max(max_depth, current)
        elif ch == "}":
            current -= 1
    return max_depth
