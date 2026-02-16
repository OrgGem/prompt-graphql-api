"""Set up Hasura relationships between tables via metadata API."""
import requests
import json

HASURA_ENDPOINT = "http://localhost:18080/v1/metadata"
ADMIN_SECRET = "myadminsecretkey"
HEADERS = {
    "Content-Type": "application/json",
    "x-hasura-admin-secret": ADMIN_SECRET,
}

def create_array_relationship(source, table, name, foreign_table, mapping):
    """Create an array relationship (one-to-many)."""
    payload = {
        "type": "pg_create_array_relationship",
        "args": {
            "source": source,
            "table": {"name": table, "schema": "public"},
            "name": name,
            "using": {
                "foreign_key_constraint_on": {
                    "table": {"name": foreign_table, "schema": "public"},
                    "columns": list(mapping.values()),
                }
            }
        }
    }
    r = requests.post(HASURA_ENDPOINT, headers=HEADERS, json=payload, timeout=10)
    print(f"  Array {table}.{name} -> {foreign_table}: {r.status_code} {r.text[:100]}")
    return r.status_code == 200

def create_object_relationship(source, table, name, column):
    """Create an object relationship (many-to-one)."""
    payload = {
        "type": "pg_create_object_relationship",
        "args": {
            "source": source,
            "table": {"name": table, "schema": "public"},
            "name": name,
            "using": {
                "foreign_key_constraint_on": column
            }
        }
    }
    r = requests.post(HASURA_ENDPOINT, headers=HEADERS, json=payload, timeout=10)
    print(f"  Object {table}.{name} via {column}: {r.status_code} {r.text[:100]}")
    return r.status_code == 200

# Set up relationships for default data source (postgres:appdb)
SOURCE = "default"
print("Setting up Hasura relationships...")

# Users -> Products (one-to-many)
print("\n1. users -> products:")
create_array_relationship(SOURCE, "users", "products", "products", {"id": "user_id"})
create_object_relationship(SOURCE, "products", "user", "user_id")

# Users -> Orders (one-to-many)
print("\n2. users -> orders:")
create_array_relationship(SOURCE, "users", "orders", "orders", {"id": "user_id"})
create_object_relationship(SOURCE, "orders", "user", "user_id")

# Users -> Articles (one-to-many) 
print("\n3. users -> articles:")
create_array_relationship(SOURCE, "users", "articles", "articles", {"id": "author_id"})
create_object_relationship(SOURCE, "articles", "author", "author_id")

# Users -> Comments (one-to-many)
print("\n4. users -> comments:")
create_array_relationship(SOURCE, "users", "comments", "comments", {"id": "user_id"})
create_object_relationship(SOURCE, "comments", "user", "user_id")

# Orders -> Order Items (one-to-many)
print("\n5. orders -> order_items:")
create_array_relationship(SOURCE, "orders", "order_items", "order_items", {"id": "order_id"})
create_object_relationship(SOURCE, "order_items", "order", "order_id")

# Products -> Order Items (one-to-many)
print("\n6. products -> order_items:")
create_array_relationship(SOURCE, "products", "order_items", "order_items", {"id": "product_id"})
create_object_relationship(SOURCE, "order_items", "product", "product_id")

# Categories -> Products (one-to-many)
print("\n7. categories -> products:")
create_array_relationship(SOURCE, "categories", "products", "products", {"id": "category_id"})
create_object_relationship(SOURCE, "products", "category", "category_id")

# Articles -> Comments (one-to-many)
print("\n8. articles -> comments:")
create_array_relationship(SOURCE, "articles", "comments", "comments", {"id": "article_id"})
create_object_relationship(SOURCE, "comments", "article", "article_id")

# Articles <-> Tags (many-to-many via article_tags)
print("\n9. articles <-> tags via article_tags:")
create_object_relationship(SOURCE, "article_tags", "article", "article_id")
create_object_relationship(SOURCE, "article_tags", "tag", "tag_id")
create_array_relationship(SOURCE, "articles", "article_tags", "article_tags", {"id": "article_id"})
create_array_relationship(SOURCE, "tags", "article_tags", "article_tags", {"id": "tag_id"})

# Categories -> Articles (one-to-many)
print("\n10. categories -> articles:")
create_array_relationship(SOURCE, "categories", "articles", "articles", {"id": "category_id"})
create_object_relationship(SOURCE, "articles", "category", "category_id")

print("\n✅ Relationship setup complete!")
