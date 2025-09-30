#!/usr/bin/env python3
"""
Basic usage example for dbbasic-tsv
Shows CRUD operations and basic queries
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dbbasic.tsv import TSV


def main():
    print("dbbasic-tsv Basic Usage Example")
    print("=" * 50)

    # Create a table
    print("\n1. Creating users table...")
    users = TSV("users", ["id", "name", "email", "age"])

    # Insert single record
    print("\n2. Inserting single record...")
    users.insert({
        "id": "1",
        "name": "Alice Smith",
        "email": "alice@example.com",
        "age": "30"
    })
    print("   ✓ Inserted Alice")

    # Insert multiple records
    print("\n3. Batch inserting records...")
    records = [
        {"id": "2", "name": "Bob Jones", "email": "bob@example.com", "age": "25"},
        {"id": "3", "name": "Charlie Brown", "email": "charlie@example.com", "age": "35"},
        {"id": "4", "name": "Diana Prince", "email": "diana@example.com", "age": "28"},
        {"id": "5", "name": "Eve Anderson", "email": "eve@example.com", "age": "32"}
    ]
    count = users.insert_many(records)
    print(f"   ✓ Inserted {count} records")

    # Query single record
    print("\n4. Querying single record...")
    user = users.query_one(id="1")
    if user:
        print(f"   Found: {user['name']} ({user['email']})")

    # Query multiple records
    print("\n5. Querying multiple records...")
    results = users.query(age="30")
    print(f"   Found {len(results)} users aged 30")
    for user in results:
        print(f"   - {user['name']}")

    # Update record
    print("\n6. Updating record...")
    updated = users.update({"id": "1"}, {"age": "31"})
    print(f"   ✓ Updated {updated} record(s)")

    # Verify update
    user = users.query_one(id="1")
    print(f"   Alice's new age: {user['age']}")

    # Count records
    print("\n7. Counting records...")
    total = users.count()
    print(f"   Total users: {total}")

    # Delete record
    print("\n8. Deleting record...")
    deleted = users.delete(id="5")
    print(f"   ✓ Deleted {deleted} record(s)")

    # List all records
    print("\n9. All remaining users:")
    for user in users.all():
        print(f"   - {user['name']} ({user['age']} years)")

    # Show table stats
    print("\n10. Table statistics:")
    stats = users.stats()
    for key, value in stats.items():
        print(f"   {key}: {value}")

    # Clean up (optional)
    print("\n11. Cleaning up...")
    users.drop()
    print("   ✓ Table dropped")

    print("\n✅ Example completed successfully!")


if __name__ == "__main__":
    main()