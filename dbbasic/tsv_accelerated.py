#!/usr/bin/env python3
"""
TSV database with optional Rust acceleration
Falls back to pure Python if Rust module not available
"""

import time
from pathlib import Path
from typing import Dict, List, Optional, Any

# Try to import Rust accelerated functions
try:
    from dbbasic_rust import (
        parse_tsv_line,
        parse_tsv_batch,
        search_index,
        filter_records,
        count_matching,
        write_tsv_batch
    )
    RUST_AVAILABLE = True
    print("🚀 Rust acceleration enabled!")
except ImportError:
    RUST_AVAILABLE = False
    print("🐍 Using pure Python implementation")

from .tsv import TSV as PurePythonTSV


class AcceleratedTSV(PurePythonTSV):
    """TSV database with optional Rust acceleration"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.rust_enabled = RUST_AVAILABLE

    def insert_many(self, records: List[Dict[str, Any]]) -> int:
        """Batch insert with Rust acceleration if available"""
        if RUST_AVAILABLE and len(records) > 100:
            # Use Rust for large batches
            start = time.perf_counter()

            # Convert records to the format Rust expects
            rust_records = [
                {col: str(rec.get(col, "")) for col in self.columns}
                for rec in records
            ]

            # Write using Rust (much faster for large batches)
            write_tsv_batch(str(self.data_file), self.columns, rust_records)

            # Update index
            for i, record in enumerate(rust_records):
                row_num = self.row_count + i
                if "id" in record:
                    self.index[record["id"]].append(row_num)

            self.row_count += len(records)
            self._save_index()

            elapsed = time.perf_counter() - start
            rate = len(records) / elapsed
            print(f"  Rust insert: {len(records)} records in {elapsed:.3f}s ({rate:,.0f} records/sec)")

            return len(records)
        else:
            # Fall back to Python for small batches
            return super().insert_many(records)

    def query(self, **conditions) -> List[Dict[str, Any]]:
        """Query with Rust acceleration if available"""
        if not conditions:
            return list(self.all())

        # Use index for primary key lookups
        if "id" in conditions and len(conditions) == 1:
            row_nums = self.index.get(conditions["id"], [])
            if not row_nums:
                return []

            # Load specific rows
            return self._load_rows(row_nums)

        # For other queries, use Rust if available for filtering
        if RUST_AVAILABLE and self.row_count > 1000:
            # Load all records
            all_records = list(self.all())

            # Use Rust for filtering (much faster)
            filtered = filter_records(all_records, conditions)
            return filtered
        else:
            # Fall back to Python
            return super().query(**conditions)

    def count(self, **conditions) -> int:
        """Count with Rust acceleration if available"""
        if not conditions:
            return self.row_count

        if RUST_AVAILABLE and self.row_count > 1000:
            # Use Rust for counting
            all_records = list(self.all())
            return count_matching(all_records, conditions)
        else:
            return super().count(**conditions)


def benchmark_rust_vs_python():
    """Compare Rust-accelerated vs pure Python performance"""
    print("\n" + "=" * 60)
    print("Rust vs Python TSV Performance")
    print("=" * 60)

    # Test with pure Python
    print("\n📊 Pure Python TSV:")
    py_tsv = PurePythonTSV("bench_python", ["id", "name", "value"])

    # Insert test
    records = [
        {"id": str(i), "name": f"test_{i}", "value": str(i * 10)}
        for i in range(10000)
    ]

    start = time.perf_counter()
    py_tsv.insert_many(records)
    py_elapsed = time.perf_counter() - start
    print(f"  Insert 10K: {py_elapsed:.3f}s ({10000/py_elapsed:,.0f} records/sec)")

    # Query test
    start = time.perf_counter()
    for i in range(100):
        py_tsv.query_one(id=str(i * 100))
    py_query_elapsed = time.perf_counter() - start
    print(f"  100 queries: {py_query_elapsed:.3f}s ({100/py_query_elapsed:,.0f} queries/sec)")

    py_tsv.drop()

    if RUST_AVAILABLE:
        # Test with Rust acceleration
        print("\n🚀 Rust-Accelerated TSV:")
        rust_tsv = AcceleratedTSV("bench_rust", ["id", "name", "value"])

        start = time.perf_counter()
        rust_tsv.insert_many(records)
        rust_elapsed = time.perf_counter() - start
        print(f"  Insert 10K: {rust_elapsed:.3f}s ({10000/rust_elapsed:,.0f} records/sec)")

        # Query test
        start = time.perf_counter()
        for i in range(100):
            rust_tsv.query_one(id=str(i * 100))
        rust_query_elapsed = time.perf_counter() - start
        print(f"  100 queries: {rust_query_elapsed:.3f}s ({100/rust_query_elapsed:,.0f} queries/sec)")

        # Show speedup
        print("\n📈 Speedup:")
        print(f"  Insert: {py_elapsed/rust_elapsed:.1f}x faster")
        print(f"  Query: {py_query_elapsed/rust_query_elapsed:.1f}x faster")

        rust_tsv.drop()
    else:
        print("\n⚠️  Install Rust module for acceleration:")
        print("  cd rust && maturin develop --release")


if __name__ == "__main__":
    benchmark_rust_vs_python()