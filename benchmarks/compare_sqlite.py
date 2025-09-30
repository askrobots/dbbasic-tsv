#!/usr/bin/env python3
"""
Performance comparison: dbbasic-tsv vs SQLite
Tests various operations and measures performance differences
"""

import os
import sys
import time
import sqlite3
import tempfile
from pathlib import Path

# Add parent to path for dbbasic import
sys.path.insert(0, str(Path(__file__).parent.parent))
from dbbasic import TSV


class Benchmark:
    """Base benchmark class"""

    def __init__(self, name: str):
        self.name = name
        self.results = {}

    def run(self, iterations: int = 1):
        """Run benchmark with timing"""
        start = time.perf_counter()
        for _ in range(iterations):
            self.execute()
        elapsed = time.perf_counter() - start
        return elapsed / iterations

    def execute(self):
        """Override in subclasses"""
        raise NotImplementedError


class TSVInsertBenchmark(Benchmark):
    """TSV batch insert benchmark"""

    def __init__(self, num_records: int):
        super().__init__(f"TSV Insert {num_records} records")
        self.num_records = num_records
        self.db = TSV("benchmark", ["id", "name", "email", "age", "created"])

    def execute(self):
        records = [
            {
                "id": str(i),
                "name": f"User_{i}",
                "email": f"user{i}@example.com",
                "age": str(20 + (i % 50)),
                "created": str(time.time())
            }
            for i in range(self.num_records)
        ]
        self.db.insert_many(records)

    def cleanup(self):
        self.db.drop()


class SQLiteInsertBenchmark(Benchmark):
    """SQLite batch insert benchmark"""

    def __init__(self, num_records: int):
        super().__init__(f"SQLite Insert {num_records} records")
        self.num_records = num_records
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.conn = sqlite3.connect(self.db_file.name)
        self.conn.execute("""
            CREATE TABLE benchmark (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                age INTEGER,
                created REAL
            )
        """)

    def execute(self):
        records = [
            (str(i), f"User_{i}", f"user{i}@example.com", 20 + (i % 50), time.time())
            for i in range(self.num_records)
        ]
        self.conn.executemany(
            "INSERT INTO benchmark VALUES (?, ?, ?, ?, ?)",
            records
        )
        self.conn.commit()

    def cleanup(self):
        self.conn.close()
        os.unlink(self.db_file.name)


class TSVQueryBenchmark(Benchmark):
    """TSV query benchmark"""

    def __init__(self, num_records: int, num_queries: int):
        super().__init__(f"TSV Query (from {num_records} records)")
        self.num_records = num_records
        self.num_queries = num_queries
        self.db = TSV("query_bench", ["id", "name", "email", "age"])

        # Pre-populate
        records = [
            {"id": str(i), "name": f"User_{i}", "email": f"user{i}@example.com", "age": str(20 + (i % 50))}
            for i in range(num_records)
        ]
        self.db.insert_many(records)

    def execute(self):
        for i in range(self.num_queries):
            query_id = str(i % self.num_records)
            result = self.db.query_one(id=query_id)

    def cleanup(self):
        self.db.drop()


class SQLiteQueryBenchmark(Benchmark):
    """SQLite query benchmark"""

    def __init__(self, num_records: int, num_queries: int):
        super().__init__(f"SQLite Query (from {num_records} records)")
        self.num_records = num_records
        self.num_queries = num_queries
        self.db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.conn = sqlite3.connect(self.db_file.name)

        # Create table and index
        self.conn.execute("""
            CREATE TABLE query_bench (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                age INTEGER
            )
        """)
        self.conn.execute("CREATE INDEX idx_id ON query_bench(id)")

        # Pre-populate
        records = [
            (str(i), f"User_{i}", f"user{i}@example.com", 20 + (i % 50))
            for i in range(num_records)
        ]
        self.conn.executemany("INSERT INTO query_bench VALUES (?, ?, ?, ?)", records)
        self.conn.commit()

    def execute(self):
        cursor = self.conn.cursor()
        for i in range(self.num_queries):
            query_id = str(i % self.num_records)
            cursor.execute("SELECT * FROM query_bench WHERE id = ?", (query_id,))
            result = cursor.fetchone()

    def cleanup(self):
        self.conn.close()
        os.unlink(self.db_file.name)


def format_time(seconds: float) -> str:
    """Format time for display"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.2f}s"


def run_comparison():
    """Run all benchmarks and compare"""
    print("=" * 70)
    print("dbbasic-tsv vs SQLite Performance Comparison")
    print("=" * 70)
    print()

    results = []

    # Test different record counts
    test_sizes = [100, 1000, 10000]

    for size in test_sizes:
        print(f"\n📊 Testing with {size:,} records")
        print("-" * 50)

        # Insert benchmarks
        print("\nInsert Performance:")

        tsv_insert = TSVInsertBenchmark(size)
        tsv_time = tsv_insert.run()
        print(f"  TSV:    {format_time(tsv_time)} ({size/tsv_time:,.0f} records/sec)")

        sqlite_insert = SQLiteInsertBenchmark(size)
        sqlite_time = sqlite_insert.run()
        print(f"  SQLite: {format_time(sqlite_time)} ({size/sqlite_time:,.0f} records/sec)")

        speedup = sqlite_time / tsv_time
        print(f"  → TSV is {speedup:.1f}x {'faster' if speedup > 1 else 'slower'}")

        results.append({
            "operation": f"Insert {size}",
            "tsv": tsv_time,
            "sqlite": sqlite_time,
            "speedup": speedup
        })

        # Cleanup
        tsv_insert.cleanup()
        sqlite_insert.cleanup()

        # Query benchmarks
        print("\nQuery Performance (100 queries):")

        tsv_query = TSVQueryBenchmark(size, 100)
        tsv_time = tsv_query.run()
        print(f"  TSV:    {format_time(tsv_time)} ({100/tsv_time:,.0f} queries/sec)")

        sqlite_query = SQLiteQueryBenchmark(size, 100)
        sqlite_time = sqlite_query.run()
        print(f"  SQLite: {format_time(sqlite_time)} ({100/sqlite_time:,.0f} queries/sec)")

        speedup = sqlite_time / tsv_time
        print(f"  → TSV is {speedup:.1f}x {'faster' if speedup > 1 else 'slower'}")

        results.append({
            "operation": f"Query {size}",
            "tsv": tsv_time,
            "sqlite": sqlite_time,
            "speedup": speedup
        })

        # Cleanup
        tsv_query.cleanup()
        sqlite_query.cleanup()

    # Summary
    print("\n" + "=" * 70)
    print("SUMMARY")
    print("=" * 70)

    print("\n| Operation      | TSV Time | SQLite Time | Speedup |")
    print("|----------------|----------|-------------|---------|")

    for r in results:
        op = r["operation"].ljust(14)
        tsv = format_time(r["tsv"]).rjust(8)
        sqlite = format_time(r["sqlite"]).rjust(11)
        speedup = f"{r['speedup']:.1f}x".rjust(7)
        print(f"| {op} | {tsv} | {sqlite} | {speedup} |")

    print("\n📝 Notes:")
    print("- TSV excels at batch inserts due to append-only design")
    print("- SQLite better for complex queries and joins")
    print("- TSV files are human-readable and Git-friendly")
    print("- SQLite requires no server but needs SQL knowledge")
    print("- TSV has zero dependencies, SQLite is built-in to Python")

    # File size comparison
    print("\n💾 Storage Comparison (10,000 records):")

    # Create TSV with data
    tsv_test = TSV("size_test", ["id", "name", "email", "age", "created"])
    records = [
        {"id": str(i), "name": f"User_{i}", "email": f"user{i}@example.com",
         "age": str(20 + (i % 50)), "created": str(time.time())}
        for i in range(10000)
    ]
    tsv_test.insert_many(records)

    tsv_size = os.path.getsize(tsv_test.data_file)
    idx_size = os.path.getsize(tsv_test.index_file) if tsv_test.index_file.exists() else 0
    tsv_total = tsv_size + idx_size

    print(f"  TSV:    {tsv_size:,} bytes (data) + {idx_size:,} bytes (index) = {tsv_total:,} bytes")

    # Create SQLite with same data
    db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    conn = sqlite3.connect(db_file.name)
    conn.execute("""
        CREATE TABLE size_test (
            id TEXT PRIMARY KEY,
            name TEXT,
            email TEXT,
            age INTEGER,
            created REAL
        )
    """)
    sqlite_records = [
        (str(i), f"User_{i}", f"user{i}@example.com", 20 + (i % 50), time.time())
        for i in range(10000)
    ]
    conn.executemany("INSERT INTO size_test VALUES (?, ?, ?, ?, ?)", sqlite_records)
    conn.commit()
    conn.close()

    sqlite_size = os.path.getsize(db_file.name)
    print(f"  SQLite: {sqlite_size:,} bytes")

    ratio = tsv_total / sqlite_size
    print(f"  → TSV uses {ratio:.1f}x {'more' if ratio > 1 else 'less'} space")

    # Cleanup
    tsv_test.drop()
    os.unlink(db_file.name)

    print("\n✅ Benchmark complete!")


if __name__ == "__main__":
    run_comparison()