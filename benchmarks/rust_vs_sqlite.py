#!/usr/bin/env python3
"""
Benchmark: Pure Python TSV vs Rust-Accelerated TSV vs SQLite
Shows real performance with actual Rust acceleration
"""

import os
import sys
import time
import sqlite3
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

# Test if Rust is available
try:
    import dbbasic_rust
    RUST_AVAILABLE = True
    print("✅ Rust acceleration module loaded!")
except ImportError:
    RUST_AVAILABLE = False
    print("❌ Rust module not available")

from dbbasic import TSV


class RustAcceleratedTSV(TSV):
    """TSV with Rust acceleration for hot paths"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rust_enabled = RUST_AVAILABLE

    def insert_many(self, records):
        """Use Rust for batch inserts"""
        if RUST_AVAILABLE and len(records) > 100:
            # Convert records to format Rust expects
            rust_records = [
                {col: str(rec.get(col, "")) for col in self.columns}
                for rec in records
            ]

            # Use Rust for fast TSV writing
            dbbasic_rust.write_tsv_batch(
                str(self.data_file),
                self.columns,
                rust_records
            )

            # Update index
            for i, record in enumerate(rust_records):
                row_num = self.row_count + i
                if "id" in record:
                    self.index[record["id"]].append(row_num)

            self.row_count += len(records)
            self._save_index()
            return len(records)
        else:
            return super().insert_many(records)

    def query(self, **conditions):
        """Use Rust for filtering if available"""
        # For indexed queries and small datasets, use parent's optimized path
        if ("id" in conditions and len(conditions) == 1) or self.row_count <= 1000:
            return super().query(**conditions)

        # Use Rust for filtering large datasets with multiple conditions
        if RUST_AVAILABLE:
            all_records = list(self.all())
            # Convert to list of dicts for Rust
            records_list = [dict(r) for r in all_records]
            filtered = dbbasic_rust.filter_records(records_list, conditions)
            return filtered
        else:
            return super().query(**conditions)


def format_time(seconds: float) -> str:
    """Format time for display"""
    if seconds < 0.001:
        return f"{seconds * 1000000:.0f}μs"
    elif seconds < 1:
        return f"{seconds * 1000:.2f}ms"
    else:
        return f"{seconds:.2f}s"


def run_comparison():
    print("=" * 80)
    print("REAL Performance: Python vs Rust-Accelerated TSV vs SQLite")
    print("=" * 80)
    print()

    test_sizes = [1000, 10000, 50000]

    for size in test_sizes:
        print(f"\n📊 Testing with {size:,} records")
        print("-" * 60)

        # Generate test data
        records = [
            {"id": str(i), "name": f"User_{i}", "email": f"user{i}@example.com",
             "age": str(20 + (i % 50)), "created": str(time.time())}
            for i in range(size)
        ]

        # Test Pure Python TSV
        print("\n🐍 Pure Python TSV:")
        py_tsv = TSV("bench_python", ["id", "name", "email", "age", "created"])

        start = time.perf_counter()
        py_tsv.insert_many(records)
        py_insert_time = time.perf_counter() - start
        py_insert_rate = size / py_insert_time
        print(f"  Insert: {format_time(py_insert_time)} ({py_insert_rate:,.0f} records/sec)")

        # Query performance
        query_count = min(100, size // 10)
        start = time.perf_counter()
        for i in range(query_count):
            py_tsv.query_one(id=str(i * 10 % size))
        py_query_time = time.perf_counter() - start
        py_query_rate = query_count / py_query_time
        print(f"  Query:  {format_time(py_query_time)} ({py_query_rate:,.0f} queries/sec)")

        py_tsv.drop()

        if RUST_AVAILABLE:
            # Test Rust-Accelerated TSV
            print("\n🚀 Rust-Accelerated TSV:")
            rust_tsv = RustAcceleratedTSV("bench_rust", ["id", "name", "email", "age", "created"])

            start = time.perf_counter()
            rust_tsv.insert_many(records)
            rust_insert_time = time.perf_counter() - start
            rust_insert_rate = size / rust_insert_time
            print(f"  Insert: {format_time(rust_insert_time)} ({rust_insert_rate:,.0f} records/sec)")

            # Query performance
            start = time.perf_counter()
            for i in range(query_count):
                rust_tsv.query_one(id=str(i * 10 % size))
            rust_query_time = time.perf_counter() - start
            rust_query_rate = query_count / rust_query_time
            print(f"  Query:  {format_time(rust_query_time)} ({rust_query_rate:,.0f} queries/sec)")

            rust_tsv.drop()

        # Test SQLite
        print("\n🗄️  SQLite:")
        db_file = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        conn = sqlite3.connect(db_file.name)
        conn.execute("""
            CREATE TABLE bench (
                id TEXT PRIMARY KEY,
                name TEXT,
                email TEXT,
                age INTEGER,
                created REAL
            )
        """)

        sqlite_records = [
            (r["id"], r["name"], r["email"], int(r["age"]), float(r["created"]))
            for r in records
        ]

        start = time.perf_counter()
        conn.executemany("INSERT INTO bench VALUES (?, ?, ?, ?, ?)", sqlite_records)
        conn.commit()
        sqlite_insert_time = time.perf_counter() - start
        sqlite_insert_rate = size / sqlite_insert_time
        print(f"  Insert: {format_time(sqlite_insert_time)} ({sqlite_insert_rate:,.0f} records/sec)")

        # SQLite query
        cursor = conn.cursor()
        start = time.perf_counter()
        for i in range(query_count):
            cursor.execute("SELECT * FROM bench WHERE id = ?", (str(i * 10 % size),))
            cursor.fetchone()
        sqlite_query_time = time.perf_counter() - start
        sqlite_query_rate = query_count / sqlite_query_time
        print(f"  Query:  {format_time(sqlite_query_time)} ({sqlite_query_rate:,.0f} queries/sec)")

        conn.close()
        os.unlink(db_file.name)

        # Show comparisons
        print("\n📈 Performance Comparison:")

        if RUST_AVAILABLE:
            print(f"\n  Rust vs Python TSV:")
            print(f"    Insert: {py_insert_time/rust_insert_time:.1f}x faster")
            print(f"    Query:  {py_query_time/rust_query_time:.1f}x faster")

            print(f"\n  Rust TSV vs SQLite:")
            rust_vs_sqlite_insert = rust_insert_rate / sqlite_insert_rate
            rust_vs_sqlite_query = rust_query_rate / sqlite_query_rate
            print(f"    Insert: {rust_vs_sqlite_insert:.1f}x {'faster' if rust_vs_sqlite_insert > 1 else 'slower'}")
            print(f"    Query:  {rust_vs_sqlite_query:.1f}x {'faster' if rust_vs_sqlite_query > 1 else 'slower'}")

        print(f"\n  Python TSV vs SQLite:")
        py_vs_sqlite_insert = py_insert_rate / sqlite_insert_rate
        py_vs_sqlite_query = py_query_rate / sqlite_query_rate
        print(f"    Insert: {py_vs_sqlite_insert:.1f}x {'faster' if py_vs_sqlite_insert > 1 else 'slower'}")
        print(f"    Query:  {py_vs_sqlite_query:.1f}x {'faster' if py_vs_sqlite_query > 1 else 'slower'}")

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)

    if RUST_AVAILABLE:
        print("""
✅ Rust acceleration is working!

The Rust module provides:
- Parallel TSV parsing with Rayon
- Fast hash-based filtering with AHash
- Buffered file I/O
- Zero-copy string handling where possible

This is just the beginning - we could accelerate even more:
- Memory-mapped files for instant loading
- SIMD-accelerated tab finding
- Compiled query predicates
- B-tree indexes in Rust
""")
    else:
        print("""
❌ Rust module not loaded. To enable:
1. cd rust
2. maturin build --release
3. pip install target/wheels/*.whl
""")


if __name__ == "__main__":
    run_comparison()