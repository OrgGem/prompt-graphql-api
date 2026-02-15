from typing import Dict, List, Optional


def _extract_tracked_table_names(metadata: Dict) -> List[str]:
    tables: List[str] = []
    for source in metadata.get("sources", []):
        for table_info in source.get("tables", []):
            table = table_info.get("table", {})
            if isinstance(table, dict):
                name = table.get("name")
            else:
                name = str(table)
            if name:
                tables.append(name)
    return tables


def plan_prompt_to_graphql(prompt: str, metadata: Dict, max_limit: int = 100) -> Dict:
    """
    Lightweight planner for Hasura CE v2:
    - chooses a tracked table using simple keyword matching
    - generates a safe aggregate-count query
    """
    prompt_lower = prompt.lower().strip()
    tracked_tables = _extract_tracked_table_names(metadata)

    selected_table: Optional[str] = None
    for table in tracked_tables:
        if table.lower() in prompt_lower:
            selected_table = table
            break

    if not selected_table and tracked_tables:
        selected_table = tracked_tables[0]

    if not selected_table:
        return {
            "success": False,
            "error": "No tracked tables found in Hasura metadata.",
            "plan_type": "unsupported",
        }

    safe_limit = max(1, min(max_limit, 1000))
    query = (
        f"query PromptQueryPlan {{ "
        f"{selected_table}_aggregate(limit: {safe_limit}) {{ aggregate {{ count }} }} "
        f"}}"
    )

    return {
        "success": True,
        "plan_type": "count_aggregate",
        "selected_table": selected_table,
        "query": query,
        "safe_limit": safe_limit,
    }


def synthesize_answer(prompt: str, selected_table: str, graphql_result: Dict) -> str:
    aggregate_data = graphql_result.get("data", {}).get(f"{selected_table}_aggregate", {})
    count = aggregate_data.get("aggregate", {}).get("count")
    if count is None:
        return f"Đã truy vấn bảng '{selected_table}' nhưng không đọc được giá trị count từ kết quả GraphQL."
    return f"Kết quả cho prompt '{prompt}': bảng '{selected_table}' hiện có {count} bản ghi."
