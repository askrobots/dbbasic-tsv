#!/usr/bin/env python3
"""
Advanced features example for dbbasic-tsv
Shows indexing, transactions, caching, and performance features
"""

import time
from pathlib import Path
from dbbasic import TSV, get_audit_log, get_query_log


def benchmark_performance():
    """Demonstrate performance capabilities"""
    print("\n📊 Performance Benchmark")
    print("-" * 40)

    db = TSV("benchmark", ["id", "data", "timestamp"])

    # Batch insert performance
    print("\nBatch insert (10,000 records):")
    records = [
        {"id": str(i), "data": f"test_{i}", "timestamp": str(time.time())}
        for i in range(10000)
    ]

    start = time.perf_counter()
    inserted = db.insert_many(records)
    elapsed = time.perf_counter() - start

    print(f"  Inserted: {inserted} records")
    print(f"  Time: {elapsed:.3f} seconds")
    print(f"  Rate: {inserted/elapsed:,.0f} records/sec")

    # Query performance with index
    print("\nIndexed query performance:")
    start = time.perf_counter()
    result = db.query_one(id="5000")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  Found: {result['data']}")
    print(f"  Time: {elapsed:.2f}ms")

    # Full scan performance
    print("\nFull scan performance:")
    start = time.perf_counter()
    results = db.query(data="test_9999")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  Found: {len(results)} record(s)")
    print(f"  Time: {elapsed:.2f}ms")

    db.drop()


def demonstrate_transactions():
    """Show atomic transactions"""
    print("\n🔄 Transactions")
    print("-" * 40)

    accounts = TSV("accounts", ["id", "name", "balance"])

    # Setup accounts
    accounts.insert({"id": "1", "name": "Alice", "balance": "1000"})
    accounts.insert({"id": "2", "name": "Bob", "balance": "1000"})

    print("\nInitial balances:")
    for acc in accounts.all():
        print(f"  {acc['name']}: ${acc['balance']}")

    # Atomic transfer
    print("\nTransferring $100 from Alice to Bob...")
    with accounts.transaction() as tx:
        # Debit Alice
        alice = tx.query_one(id="1")
        new_balance = str(int(alice["balance"]) - 100)
        tx.update({"id": "1"}, {"balance": new_balance})

        # Credit Bob
        bob = tx.query_one(id="2")
        new_balance = str(int(bob["balance"]) + 100)
        tx.update({"id": "2"}, {"balance": new_balance})

    print("\nFinal balances:")
    for acc in accounts.all():
        print(f"  {acc['name']}: ${acc['balance']}")

    accounts.drop()


def show_audit_logging():
    """Demonstrate audit logging"""
    print("\n📝 Audit Logging")
    print("-" * 40)

    # Enable audit logging
    products = TSV("products", ["id", "name", "price"], audit=True)

    # Perform operations
    products.insert({"id": "1", "name": "Widget", "price": "9.99"})
    products.update({"id": "1"}, {"price": "12.99"})
    products.query(name="Widget")
    products.delete(id="1")

    # Get audit log
    audit = get_audit_log()
    print("\nRecent operations:")
    for entry in audit.tail(4):
        print(f"  {entry['operation']:8} {entry['table']:10} Success: {entry['success']}")

    # Get statistics
    stats = audit.get_stats()
    print(f"\nTotal operations: {stats['total_operations']}")
    print(f"Error rate: {stats['error_rate']:.1%}")

    products.drop()


def demonstrate_indexing():
    """Show custom indexing"""
    print("\n🔍 Custom Indexing")
    print("-" * 40)

    users = TSV("users", ["id", "email", "username", "created"])

    # Insert test data
    test_users = [
        {"id": "1", "email": "alice@example.com", "username": "alice", "created": "2024-01-01"},
        {"id": "2", "email": "bob@example.com", "username": "bob", "created": "2024-01-02"},
        {"id": "3", "email": "charlie@example.com", "username": "charlie", "created": "2024-01-03"},
    ]
    users.insert_many(test_users)

    print("\nBefore creating email index:")
    start = time.perf_counter()
    result = users.query_one(email="bob@example.com")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  Query by email: {elapsed:.2f}ms (full scan)")

    # Create index on email
    print("\nCreating index on email column...")
    users.create_index("email")

    print("\nAfter creating email index:")
    start = time.perf_counter()
    result = users.query_one(email="bob@example.com")
    elapsed = (time.perf_counter() - start) * 1000
    print(f"  Query by email: {elapsed:.2f}ms (indexed)")

    users.drop()


def show_query_performance():
    """Track query performance"""
    print("\n⚡ Query Performance Tracking")
    print("-" * 40)

    orders = TSV("orders", ["id", "customer", "total", "status"])

    # Insert test data
    for i in range(100):
        orders.insert({
            "id": str(i),
            "customer": f"customer_{i % 10}",
            "total": str(100 + i),
            "status": "pending" if i % 2 == 0 else "completed"
        })

    # Perform various queries
    print("\nRunning queries...")
    orders.query_one(id="50")  # Indexed query
    orders.query(status="completed")  # Full scan
    orders.query(customer="customer_5")  # Full scan
    orders.query_one(id="75")  # Cache hit

    # Get query statistics
    qlog = get_query_log()
    stats = qlog.get_stats()

    print(f"\nQuery Statistics:")
    print(f"  Total queries: {stats['total_queries']}")
    print(f"  Avg time: {stats['avg_time_ms']:.2f}ms")
    print(f"  Cache hit rate: {stats['cache_hit_rate']:.1%}")
    print(f"  Index hit rate: {stats['index_hit_rate']:.1%}")
    print(f"  Full scan rate: {stats['full_scan_rate']:.1%}")

    orders.drop()


def demonstrate_backup_restore():
    """Show backup and restore"""
    print("\n💾 Backup and Restore")
    print("-" * 40)

    # Create and populate table
    config = TSV("config", ["key", "value", "description"])
    config.insert({"key": "app.name", "value": "MyApp", "description": "Application name"})
    config.insert({"key": "app.version", "value": "1.0.0", "description": "Version number"})
    config.insert({"key": "db.timeout", "value": "30", "description": "Database timeout"})

    print(f"\nOriginal records: {config.count()}")

    # Backup
    backup_path = Path("./backup_test")
    print(f"\nBacking up to {backup_path}...")
    config.backup(backup_path)

    # Modify data
    config.delete(key="db.timeout")
    config.update({"key": "app.version"}, {"value": "2.0.0"})
    print(f"\nAfter modifications: {config.count()} records")

    # Restore
    print(f"\nRestoring from backup...")
    config.restore(backup_path)
    print(f"After restore: {config.count()} records")

    # Verify data
    version = config.query_one(key="app.version")
    print(f"App version: {version['value']}")

    # Cleanup
    config.drop()
    import shutil
    shutil.rmtree(backup_path, ignore_errors=True)


def main():
    print("=" * 50)
    print("dbbasic-tsv Advanced Features Demo")
    print("=" * 50)

    # Run all demonstrations
    benchmark_performance()
    demonstrate_transactions()
    show_audit_logging()
    demonstrate_indexing()
    show_query_performance()
    demonstrate_backup_restore()

    print("\n" + "=" * 50)
    print("✅ All demonstrations completed!")
    print("=" * 50)


if __name__ == "__main__":
    main()