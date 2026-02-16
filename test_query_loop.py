"""Quick test script for the LLM query generation loop."""
import requests
import json
import sys

BASE = "http://localhost:8765"
KEY = "my-dashboard-secret-2024"
HEADERS = {"X-Dashboard-Key": KEY, "Content-Type": "application/json"}

def test_chat(message, app_id="sampledb"):
    print(f"\n{'='*60}")
    print(f"Q: {message}")
    print(f"App: {app_id}")
    print(f"{'='*60}")
    
    r = requests.post(
        f"{BASE}/api/chat",
        json={"message": message, "mode": "llm", "app_id": app_id},
        headers=HEADERS,
        timeout=120,
    )
    d = r.json()
    print(f"Status: {r.status_code}")
    print(f"Success: {d.get('success')}")
    
    if d.get("query_generated"):
        print(f"\n📝 Generated Query:")
        print(d["query_generated"])
    
    if d.get("query_results"):
        print(f"\n📊 Query Results:")
        print(json.dumps(d["query_results"], indent=2, ensure_ascii=False)[:500])
    
    print(f"\n💬 Answer:")
    print(d.get("content", d.get("error", "N/A"))[:500])
    
    if d.get("usage"):
        u = d["usage"]
        print(f"\n📈 Tokens: {u.get('total_tokens', 'N/A')}")
    
    return d

# Test 1: Health check
print("Testing health...")
r = requests.get(f"{BASE}/api/health", headers=HEADERS, timeout=10)
print(f"Health: {r.status_code} {r.json().get('status')}")

# Test 2: Simple count
test_chat("how many users are there?")

# Test 3: Cross-table analytical query
test_chat("user nào có nhiều sản phẩm nhất?")

# Test 4: Aggregation
test_chat("what is the total value of all orders?")

print("\n\n✅ All tests completed!")
