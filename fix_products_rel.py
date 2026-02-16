"""Create users→products relationship using manual configuration."""
import requests
import json

HASURA_META = "http://localhost:18080/v1/metadata"
SECRET = "myadminsecretkey"
HEADERS = {"Content-Type": "application/json", "x-hasura-admin-secret": SECRET}

# First check what columns products table has
print("=== Products columns ===")
r = requests.post("http://localhost:18080/v1/graphql", headers=HEADERS, json={
    "query": '{ __type(name: "products") { fields { name type { name kind } } } }'
}, timeout=10)
d = r.json()
if d.get("data", {}).get("__type"):
    for f in d["data"]["__type"]["fields"]:
        print(f"  {f['name']}: {f['type']['kind']} {f['type'].get('name','')}")
else:
    print("  Products type NOT FOUND")
    exit(1)

# Check if products has user_id column
cols = [f["name"] for f in d["data"]["__type"]["fields"]]
print(f"\nAll columns: {cols}")

if "user_id" in cols:
    print("\n✅ products.user_id exists! Creating manual relationship...")

    # Create array relationship: users.products via manual config
    payload = {
        "type": "pg_create_array_relationship",
        "args": {
            "source": "sampledb",
            "table": {"name": "users", "schema": "public"},
            "name": "products",
            "using": {
                "manual_configuration": {
                    "remote_table": {"name": "products", "schema": "public"},
                    "column_mapping": {"id": "user_id"}
                }
            }
        }
    }
    r = requests.post(HASURA_META, headers=HEADERS, json=payload, timeout=10)
    print(f"  Create users.products: {r.status_code} {r.text[:200]}")

    # Create object relationship: products.user via manual config
    payload2 = {
        "type": "pg_create_object_relationship",
        "args": {
            "source": "sampledb",
            "table": {"name": "products", "schema": "public"},
            "name": "user",
            "using": {
                "manual_configuration": {
                    "remote_table": {"name": "users", "schema": "public"},
                    "column_mapping": {"user_id": "id"}
                }
            }
        }
    }
    r = requests.post(HASURA_META, headers=HEADERS, json=payload2, timeout=10)
    print(f"  Create products.user: {r.status_code} {r.text[:200]}")

    # Verify
    print("\n=== Verify: users_order_by fields ===")
    r = requests.post("http://localhost:18080/v1/graphql", headers=HEADERS, json={
        "query": '{ __type(name: "users_order_by") { inputFields { name } } }'
    }, timeout=10)
    data = r.json()
    fields = [f["name"] for f in data["data"]["__type"]["inputFields"]]
    print(f"  {fields}")
    print(f"  products_aggregate in order_by: {'products_aggregate' in fields}")

    # Test cross-table query
    print("\n=== Test: users with products count ===")
    test_query = """
    query {
      users(order_by: {products_aggregate: {count: desc}}, limit: 3) {
        id
        username
        full_name
        products_aggregate {
          aggregate { count }
        }
      }
    }
    """
    r = requests.post("http://localhost:18080/v1/graphql", headers=HEADERS, json={"query": test_query}, timeout=10)
    d = r.json()
    if d.get("errors"):
        print(f"  ERROR: {d['errors'][0].get('message','')}")
    else:
        print(json.dumps(d["data"], indent=2, ensure_ascii=False))

else:
    print("\n❌ products.user_id NOT found. Cannot create relationship.")
    # Check for alternative FK columns
    fk_candidates = [c for c in cols if c.endswith("_id")]
    print(f"  FK candidates: {fk_candidates}")
