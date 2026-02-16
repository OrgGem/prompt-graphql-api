"""Check users table schema in Hasura to see if relationships are visible."""
import requests
import json

HASURA_GQL = "http://localhost:18080/v1/graphql"
HASURA_META = "http://localhost:18080/v1/metadata"
SECRET = "myadminsecretkey"
HEADERS = {"Content-Type": "application/json", "x-hasura-admin-secret": SECRET}

# Check 1: What fields does 'users' type expose?
print("=== Users type fields ===")
r = requests.post(HASURA_GQL, headers=HEADERS, json={
    "query": '{ __type(name: "users") { fields { name type { name kind } } } }'
}, timeout=10)
fields = r.json()["data"]["__type"]["fields"]
for f in fields:
    print(f"  {f['name']}: {f['type']['kind']} {f['type'].get('name','')}")

# Check 2: What does users_order_by look like?
print("\n=== users_order_by fields ===")
r = requests.post(HASURA_GQL, headers=HEADERS, json={
    "query": '{ __type(name: "users_order_by") { inputFields { name } } }'
}, timeout=10)
data = r.json()
if data.get("data", {}).get("__type"):
    for f in data["data"]["__type"]["inputFields"]:
        print(f"  {f['name']}")
else:
    print("  NOT FOUND")

# Check 3: Metadata — users relationships
print("\n=== Metadata: users relationships ===")
r = requests.post(HASURA_META, headers=HEADERS, json={
    "type": "export_metadata", "args": {}
}, timeout=10)
m = r.json()
for s in m.get("sources", []):
    if s["name"] == "sampledb":
        for t in s.get("tables", []):
            if t["table"]["name"] == "users":
                print(json.dumps(t, indent=2))
                break

# Check 4: Try simple cross-table query
print("\n=== Test: users with products count ===")
test_query = """
query {
  users {
    id
    name
    products_aggregate {
      aggregate { count }
    }
  }
}
"""
r = requests.post(HASURA_GQL, headers=HEADERS, json={"query": test_query}, timeout=10)
d = r.json()
if d.get("errors"):
    print(f"  ERROR: {d['errors'][0].get('message','')}")
else:
    print(json.dumps(d["data"], indent=2))
