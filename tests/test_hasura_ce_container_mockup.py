import os
import time
import unittest

import requests

from pgql.api.hasura_ce_client import HasuraCEClient
from pgql.api.hasura_query_planner import plan_prompt_to_graphql, synthesize_answer


class HasuraCEMockupContainerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.endpoint = os.getenv("HASURA_GRAPHQL_ENDPOINT", "http://localhost:18080/v1/graphql")
        cls.admin_secret = os.getenv("HASURA_GRAPHQL_ADMIN_SECRET", "testsecret")
        cls.client = HasuraCEClient(graphql_endpoint=cls.endpoint, admin_secret=cls.admin_secret, timeout=10)
        cls._wait_hasura_ready()
        cls._track_customers_table()

    @classmethod
    def _wait_hasura_ready(cls, max_wait=60):
        metadata_endpoint = cls.endpoint.rsplit("/v1/graphql", 1)[0] + "/healthz"
        started = time.time()
        while time.time() - started < max_wait:
            try:
                response = requests.get(metadata_endpoint, timeout=5)
                if response.status_code == 200:
                    return
            except requests.RequestException:
                pass
            time.sleep(2)
        raise RuntimeError("Hasura mockup container is not ready in time")

    @classmethod
    def _track_customers_table(cls):
        metadata_endpoint = cls.endpoint.rsplit("/v1/graphql", 1)[0] + "/v1/metadata"
        payload = {
            "type": "pg_track_table",
            "args": {
                "source": "default",
                "table": {"schema": "public", "name": "customers"},
            },
        }
        requests.post(
            metadata_endpoint,
            headers={"x-hasura-admin-secret": cls.admin_secret},
            json=payload,
            timeout=10,
        )

    def test_prompt_to_query_flow_with_hasura_container(self):
        metadata = self.client.export_metadata()
        plan = plan_prompt_to_graphql("count customers", metadata, max_limit=10)
        self.assertTrue(plan["success"])
        result = self.client.execute_graphql(plan["query"])
        answer = synthesize_answer("count customers", plan["selected_table"], result)

        self.assertIn("customers", answer)
        self.assertIn("3", answer)


if __name__ == "__main__":
    unittest.main()
