import unittest

from promptql_mcp_server.api.hasura_query_planner import plan_prompt_to_graphql, synthesize_answer


class HasuraQueryPlannerTests(unittest.TestCase):
    def test_plan_uses_matching_table(self):
        metadata = {
            "sources": [
                {"tables": [{"table": {"schema": "public", "name": "customers"}}]}
            ]
        }
        plan = plan_prompt_to_graphql("count customers", metadata, max_limit=10)
        self.assertTrue(plan["success"])
        self.assertEqual(plan["selected_table"], "customers")
        self.assertIn("customers_aggregate", plan["query"])

    def test_plan_falls_back_to_first_table(self):
        metadata = {"sources": [{"tables": [{"table": {"name": "orders"}}]}]}
        plan = plan_prompt_to_graphql("something else", metadata)
        self.assertTrue(plan["success"])
        self.assertEqual(plan["selected_table"], "orders")

    def test_synthesize_answer_reads_count(self):
        answer = synthesize_answer(
            prompt="count customers",
            selected_table="customers",
            graphql_result={"data": {"customers_aggregate": {"aggregate": {"count": 3}}}},
        )
        self.assertIn("3", answer)


if __name__ == "__main__":
    unittest.main()
