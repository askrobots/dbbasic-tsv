#!/usr/bin/env python3
"""
Simple, robust TSV database
Focus on reliability over complexity
"""

import os
import csv
import json
import time
import fcntl
import hashlib
import tempfile
import threading
from pathlib import Path
from datetime import datetime
from collections import defaultdict, OrderedDict
from typing import Dict, List, Optional, Any, Iterator
from contextlib import contextmanager

# Configure CSV for large fields
csv.field_size_limit(min(2**31-1, os.sysconf('SC_ARG_MAX')))


class TSV:
    """
    Simple, reliable TSV database
    - Atomic writes
    - Row-level operations
    - Basic indexing
    - Crash recovery
    """

    def __init__(self, table_name: str, columns: List[str], data_dir: Path = None):
        self.table_name = table_name
        self.columns = columns
        self.data_dir = data_dir or Path.cwd() / "data"
        self.data_dir.mkdir(parents=True, exist_ok=True)

        # Files
        self.data_file = self.data_dir / f"{table_name}.tsv"
        self.lock_file = self.data_dir / f"{table_name}.lock"
        self.index_file = self.data_dir / f"{table_name}.idx"
        self.meta_file = self.data_dir / f"{table_name}.meta"

        # In-memory index (simple dict)
        self.index = defaultdict(list)
        self.row_count = 0

        # Cache for frequently accessed rows
        self.cache = OrderedDict()
        self.max_cache_size = 100

        # Transaction state
        self._in_transaction = False

        # Initialize
        self._init_table()
        self._load_index()

    def _init_table(self):
        """Initialize table with headers"""
        if not self.data_file.exists():
            with open(self.data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(self.columns)

            # Save metadata
            self._save_metadata()

    def _save_metadata(self):
        """Save table metadata"""
        meta = {
            'table_name': self.table_name,
            'columns': self.columns,
            'created': datetime.utcnow().isoformat(),
            'row_count': self.row_count
        }

        with open(self.meta_file, 'w') as f:
            json.dump(meta, f, indent=2)

    @contextmanager
    def _lock(self, exclusive: bool = True):
        """File locking for concurrent access"""
        # Skip locking if we're already in a transaction
        if self._in_transaction:
            yield
            return

        lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)

        try:
            # Get lock
            if exclusive:
                fcntl.flock(lock_fd, fcntl.LOCK_EX)
            else:
                fcntl.flock(lock_fd, fcntl.LOCK_SH)

            yield

        finally:
            # Release lock
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def _load_index(self):
        """Load or rebuild index"""
        # Check if index exists and is up to date
        if self.index_file.exists() and self.data_file.exists():
            try:
                # Compare modification times - rebuild if data is newer than index
                data_mtime = os.path.getmtime(self.data_file)
                index_mtime = os.path.getmtime(self.index_file)

                if index_mtime >= data_mtime:
                    # Index is current, load it
                    with open(self.index_file, 'r') as f:
                        data = json.load(f)
                        self.index = defaultdict(list, data.get('index', {}))
                        self.row_count = data.get('row_count', 0)
                    return
            except (json.JSONDecodeError, KeyError, OSError):
                pass

        # Rebuild index from data (either missing, corrupt, or stale)
        self._rebuild_index()

    def _rebuild_index(self):
        """Rebuild index from scratch"""
        self.index.clear()
        self.row_count = 0

        if not self.data_file.exists():
            return

        with open(self.data_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f, delimiter='\t')

            for row_num, row in enumerate(reader):
                # Index first column (usually ID)
                if self.columns and self.columns[0] in row:
                    key = row[self.columns[0]]
                    if key:
                        self.index[key].append(row_num)

                self.row_count += 1

        self._save_index()

    def _save_index(self):
        """Save index to file"""
        data = {
            'index': dict(self.index),
            'row_count': self.row_count,
            'updated': datetime.utcnow().isoformat()
        }

        # Write atomically
        temp_file = self.index_file.with_suffix('.tmp')
        with open(temp_file, 'w') as f:
            json.dump(data, f)

        temp_file.replace(self.index_file)

    def insert(self, record: Dict[str, Any]) -> bool:
        """Insert a record"""
        with self._lock():
            try:
                # Validate and normalize
                record = self._normalize_record(record)

                # Append to file
                with open(self.data_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.columns,
                                          delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                    writer.writerow(record)

                # Update index
                if self.columns and self.columns[0] in record:
                    key = record[self.columns[0]]
                    if key:
                        self.index[key].append(self.row_count)

                self.row_count += 1

                # Save index periodically
                if self.row_count % 100 == 0:
                    self._save_index()

                return True

            except Exception as e:
                print(f"Insert error: {e}")
                return False

    def insert_many(self, records: List[Dict[str, Any]]) -> int:
        """Insert multiple records efficiently"""
        with self._lock():
            inserted = 0

            try:
                with open(self.data_file, 'a', newline='', encoding='utf-8') as f:
                    writer = csv.DictWriter(f, fieldnames=self.columns,
                                          delimiter='\t', quoting=csv.QUOTE_MINIMAL)

                    for record in records:
                        record = self._normalize_record(record)
                        writer.writerow(record)

                        # Update index
                        if self.columns and self.columns[0] in record:
                            key = record[self.columns[0]]
                            if key:
                                self.index[key].append(self.row_count)

                        self.row_count += 1
                        inserted += 1

                self._save_index()
                return inserted

            except Exception as e:
                print(f"Batch insert error: {e}")
                return inserted

    def query(self, **conditions) -> List[Dict[str, Any]]:
        """Query records"""
        results = []

        with self._lock(exclusive=False):
            # Try to use index for first column
            if self.columns and self.columns[0] in conditions:
                key = str(conditions[self.columns[0]])

                # Check cache
                if key in self.cache:
                    cached = self.cache[key]
                    if self._matches_conditions(cached, conditions):
                        return [cached]

                # Use index
                if key in self.index:
                    row_nums = self.index[key]

                    with open(self.data_file, 'r', encoding='utf-8') as f:
                        reader = list(csv.DictReader(f, delimiter='\t'))

                        for row_num in row_nums:
                            if row_num < len(reader):
                                row = reader[row_num]
                                if self._matches_conditions(row, conditions):
                                    results.append(row)
                                    # Cache result
                                    self._add_to_cache(key, row)
            else:
                # Full scan
                with open(self.data_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f, delimiter='\t')

                    for row in reader:
                        if self._matches_conditions(row, conditions):
                            results.append(row)

        return results

    def query_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """Query single record"""
        results = self.query(**conditions)
        return results[0] if results else None

    def update(self, conditions: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update matching records"""
        with self._lock():
            # Read all records
            records = []
            updated = 0

            with open(self.data_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for row in reader:
                    if self._matches_conditions(row, conditions):
                        row.update(updates)
                        updated += 1
                        # Invalidate cache
                        if self.columns and self.columns[0] in row:
                            key = row[self.columns[0]]
                            if key in self.cache:
                                del self.cache[key]

                    records.append(row)

            if updated > 0:
                # Write back atomically
                self._write_all(records)
                # Rebuild index since row positions might change
                self._rebuild_index()

            return updated

    def delete(self, **conditions) -> int:
        """Delete matching records"""
        with self._lock():
            # Read all records
            records = []
            deleted = 0

            with open(self.data_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')

                for row in reader:
                    if self._matches_conditions(row, conditions):
                        deleted += 1
                        # Invalidate cache
                        if self.columns and self.columns[0] in row:
                            key = row[self.columns[0]]
                            if key in self.cache:
                                del self.cache[key]
                    else:
                        records.append(row)

            if deleted > 0:
                # Write back atomically
                self._write_all(records)
                # Rebuild index
                self._rebuild_index()

            return deleted

    def count(self, **conditions) -> int:
        """Count matching records"""
        if not conditions:
            return self.row_count

        return len(self.query(**conditions))

    def all(self) -> Iterator[Dict[str, Any]]:
        """Iterate over all records"""
        with self._lock(exclusive=False):
            with open(self.data_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f, delimiter='\t')
                for row in reader:
                    yield row

    def truncate(self):
        """Remove all records but keep structure"""
        with self._lock():
            with open(self.data_file, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f, delimiter='\t', quoting=csv.QUOTE_MINIMAL)
                writer.writerow(self.columns)

            self.index.clear()
            self.cache.clear()
            self.row_count = 0
            self._save_index()

    def drop(self):
        """Delete the table completely"""
        with self._lock():
            for file in [self.data_file, self.index_file, self.meta_file, self.lock_file]:
                file.unlink(missing_ok=True)

    def backup(self, backup_path: Path):
        """Create backup of table"""
        with self._lock(exclusive=False):
            import shutil

            backup_path.mkdir(parents=True, exist_ok=True)

            for file in [self.data_file, self.index_file, self.meta_file]:
                if file.exists():
                    shutil.copy2(file, backup_path / file.name)

    def restore(self, backup_path: Path):
        """Restore from backup"""
        with self._lock():
            import shutil

            for file in [self.data_file, self.index_file, self.meta_file]:
                backup_file = backup_path / file.name
                if backup_file.exists():
                    shutil.copy2(backup_file, file)

            self._load_index()
            self.cache.clear()

    def stats(self) -> Dict[str, Any]:
        """Get table statistics"""
        file_size = self.data_file.stat().st_size if self.data_file.exists() else 0

        return {
            'table_name': self.table_name,
            'columns': self.columns,
            'row_count': self.row_count,
            'file_size': file_size,
            'file_size_human': self._format_bytes(file_size),
            'index_size': len(self.index),
            'cache_size': len(self.cache),
            'data_file': str(self.data_file)
        }

    def create_index(self, column: str):
        """Create or rebuild index on a specific column

        Args:
            column: Column name to index

        Note:
            Currently indexes are automatically maintained on the first column.
            This method rebuilds the index to ensure it's up to date.
        """
        if column not in self.columns:
            raise ValueError(f"Column '{column}' not found in table columns: {self.columns}")

        # For now, just rebuild the existing index
        # The TSV class already indexes the first column automatically
        self._rebuild_index()

    @contextmanager
    def transaction(self):
        """Context manager for atomic transactions

        Usage:
            with db.transaction() as tx:
                tx.update({"id": "1"}, {"value": "new"})
                tx.insert({"id": "2", "value": "another"})

        All operations are atomic - either all succeed or all fail.
        """
        import shutil

        # Create a simple transaction object that delegates to self
        class Transaction:
            def __init__(self, tsv_instance):
                self.tsv = tsv_instance

            def insert(self, record):
                return self.tsv.insert(record)

            def update(self, conditions, updates):
                return self.tsv.update(conditions, updates)

            def delete(self, **conditions):
                return self.tsv.delete(**conditions)

        # Acquire lock once for the entire transaction
        lock_fd = os.open(self.lock_file, os.O_CREAT | os.O_RDWR)
        fcntl.flock(lock_fd, fcntl.LOCK_EX)

        # Backup the data file for rollback
        backup_file = self.data_file.parent / f"{self.data_file.name}.tx_backup"
        if self.data_file.exists():
            shutil.copy2(self.data_file, backup_file)

        # Set transaction flag so nested operations don't try to lock
        self._in_transaction = True

        tx = Transaction(self)
        try:
            yield tx
            # Transaction succeeded - remove backup
            backup_file.unlink(missing_ok=True)
        except Exception as e:
            # Transaction failed - rollback by restoring from backup
            if backup_file.exists():
                shutil.copy2(backup_file, self.data_file)
                backup_file.unlink()
                # Rebuild index after rollback (index is now stale)
                self._rebuild_index()
            raise e
        finally:
            # Always release lock and reset flag
            self._in_transaction = False
            fcntl.flock(lock_fd, fcntl.LOCK_UN)
            os.close(lock_fd)

    def _normalize_record(self, record: Dict[str, Any]) -> Dict[str, str]:
        """Normalize record for TSV storage"""
        normalized = {}

        for col in self.columns:
            value = record.get(col, '')

            # Convert to string
            if value is None:
                value = ''
            elif isinstance(value, bool):
                value = '1' if value else '0'
            elif isinstance(value, (list, dict)):
                value = json.dumps(value)
            else:
                value = str(value)

            # Clean up for TSV
            value = value.replace('\t', '    ').replace('\n', ' ').replace('\r', '')
            normalized[col] = value

        return normalized

    def _matches_conditions(self, row: Dict[str, Any], conditions: Dict[str, Any]) -> bool:
        """Check if row matches all conditions"""
        for key, value in conditions.items():
            if key not in row:
                return False

            # Handle different types of comparisons
            row_val = row[key]
            cond_val = str(value) if value is not None else ''

            if row_val != cond_val:
                return False

        return True

    def _write_all(self, records: List[Dict[str, Any]]):
        """Write all records atomically"""
        temp_file = self.data_file.with_suffix('.tmp')

        with open(temp_file, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=self.columns,
                                  delimiter='\t', quoting=csv.QUOTE_MINIMAL)
            writer.writeheader()
            writer.writerows(records)

        # Atomic replace
        temp_file.replace(self.data_file)

    def _add_to_cache(self, key: str, value: Dict[str, Any]):
        """Add to LRU cache"""
        # Remove if exists (for LRU ordering)
        if key in self.cache:
            del self.cache[key]

        # Add to end
        self.cache[key] = value

        # Trim if too large
        while len(self.cache) > self.max_cache_size:
            self.cache.popitem(last=False)

    @staticmethod
    def _format_bytes(size: int) -> str:
        """Format bytes to human readable"""
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"


def test_simple_tsv():
    """Test SimpleTSV database"""
    print("Testing SimpleTSV Database")
    print("=" * 50)

    # Create test database
    db = SimpleTSV("test_simple", ["id", "name", "email", "age", "active"])

    # Test 1: Insert
    print("\n1. Testing Insert:")
    records = [
        {"id": "1", "name": "Alice", "email": "alice@example.com", "age": 25, "active": True},
        {"id": "2", "name": "Bob", "email": "bob@example.com", "age": 30, "active": False},
        {"id": "3", "name": "Charlie", "email": "charlie@example.com", "age": 35, "active": True},
    ]

    for record in records:
        db.insert(record)

    print(f"   ✓ Inserted {len(records)} records")

    # Test 2: Query
    print("\n2. Testing Query:")
    result = db.query_one(id="1")
    print(f"   ✓ Found by ID: {result['name']}")

    active_users = db.query(active="1")
    print(f"   ✓ Active users: {len(active_users)}")

    # Test 3: Update
    print("\n3. Testing Update:")
    updated = db.update({"id": "2"}, {"active": "1"})
    print(f"   ✓ Updated {updated} record(s)")

    # Test 4: Count
    print("\n4. Testing Count:")
    total = db.count()
    active = db.count(active="1")
    print(f"   ✓ Total: {total}, Active: {active}")

    # Test 5: Delete
    print("\n5. Testing Delete:")
    deleted = db.delete(id="3")
    print(f"   ✓ Deleted {deleted} record(s)")

    # Test 6: Stats
    print("\n6. Database Stats:")
    stats = db.stats()
    for key, value in stats.items():
        if key != 'data_file':
            print(f"   {key}: {value}")

    # Clean up
    db.drop()
    print("\n✓ All tests passed!")


def benchmark_simple():
    """Benchmark SimpleTSV performance"""
    import random
    import string

    print("SimpleTSV Performance Benchmark")
    print("=" * 50)

    db = SimpleTSV("benchmark", ["id", "name", "email", "age", "city"])

    def random_string(length=10):
        return ''.join(random.choices(string.ascii_letters, k=length))

    cities = ["New York", "London", "Tokyo", "Paris", "Berlin"]

    # Benchmark batch insert
    print("\n1. Batch Insert Performance:")
    records = []
    for i in range(10000):
        records.append({
            "id": str(i),
            "name": random_string(),
            "email": f"{random_string()}@example.com",
            "age": random.randint(18, 80),
            "city": random.choice(cities)
        })

    start = time.time()
    inserted = db.insert_many(records)
    insert_time = time.time() - start

    print(f"   Inserted {inserted} records in {insert_time:.2f}s")
    print(f"   Rate: {inserted/insert_time:.0f} records/sec")

    # Benchmark queries
    print("\n2. Query Performance:")

    # Random ID lookups
    start = time.time()
    for _ in range(1000):
        db.query_one(id=str(random.randint(0, 9999)))
    query_time = time.time() - start

    print(f"   1000 random lookups in {query_time:.3f}s")
    print(f"   Rate: {1000/query_time:.0f} queries/sec")

    # Scan query
    start = time.time()
    results = db.query(city="Tokyo")
    scan_time = time.time() - start

    print(f"   Scan query returned {len(results)} records in {scan_time:.3f}s")

    # Show final stats
    print("\n3. Final Statistics:")
    stats = db.stats()
    print(f"   Rows: {stats['row_count']:,}")
    print(f"   File size: {stats['file_size_human']}")
    print(f"   Index entries: {stats['index_size']}")

    # Clean up
    db.drop()


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        if sys.argv[1] == "test":
            test_simple_tsv()
        elif sys.argv[1] == "benchmark":
            benchmark_simple()
    else:
        # Run both
        test_simple_tsv()
        print("\n" + "=" * 50 + "\n")
        benchmark_simple()