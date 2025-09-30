#!/usr/bin/env python3
"""
BigTable-inspired TSV database
Implements SSTable/Memtable concepts with TSV files

Architecture:
- Memtable: In-memory buffer for writes
- SSTables: Immutable TSV files on disk (sorted)
- Compaction: Merge and cleanup old files
- Bloom filters: Fast negative lookups
- Sharding: Automatic partitioning for scale
"""

import os
import time
import json
import bisect
import hashlib
import threading
from pathlib import Path
from typing import Dict, List, Optional, Any, Iterator, Tuple
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
import struct

# Try to use Rust acceleration if available
try:
    import dbbasic_rust
    RUST_AVAILABLE = True
except ImportError:
    RUST_AVAILABLE = False


class BloomFilter:
    """Probabilistic data structure for fast negative lookups"""

    def __init__(self, size: int = 10000, num_hashes: int = 3):
        self.size = size
        self.num_hashes = num_hashes
        self.bits = [False] * size
        self.count = 0

    def _hash(self, item: str, seed: int) -> int:
        """Generate hash with seed"""
        h = hashlib.md5(f"{item}{seed}".encode()).digest()
        return struct.unpack('I', h[:4])[0] % self.size

    def add(self, item: str):
        """Add item to filter"""
        for i in range(self.num_hashes):
            self.bits[self._hash(item, i)] = True
        self.count += 1

    def might_contain(self, item: str) -> bool:
        """Check if item might be in set (can have false positives)"""
        return all(self.bits[self._hash(item, i)] for i in range(self.num_hashes))

    def save(self, path: Path):
        """Save bloom filter to disk"""
        with open(path, 'wb') as f:
            # Write header
            f.write(struct.pack('III', self.size, self.num_hashes, self.count))
            # Write bits as bytes
            byte_array = bytearray((len(self.bits) + 7) // 8)
            for i, bit in enumerate(self.bits):
                if bit:
                    byte_array[i // 8] |= 1 << (i % 8)
            f.write(byte_array)

    @classmethod
    def load(cls, path: Path) -> 'BloomFilter':
        """Load bloom filter from disk"""
        with open(path, 'rb') as f:
            size, num_hashes, count = struct.unpack('III', f.read(12))
            bf = cls(size, num_hashes)
            bf.count = count

            # Read bits
            byte_array = f.read()
            for i in range(size):
                byte_idx = i // 8
                bit_idx = i % 8
                if byte_idx < len(byte_array):
                    bf.bits[i] = bool(byte_array[byte_idx] & (1 << bit_idx))

            return bf


@dataclass
class SSTable:
    """Immutable sorted string table (TSV file on disk)"""
    path: Path
    min_key: str
    max_key: str
    record_count: int
    bloom_filter: Optional[BloomFilter] = None
    creation_time: float = 0
    level: int = 0  # For leveled compaction

    def contains_key_range(self, key: str) -> bool:
        """Check if key might be in this SSTable's range"""
        return self.min_key <= key <= self.max_key

    def might_contain_key(self, key: str) -> bool:
        """Quick check using bloom filter"""
        if self.bloom_filter:
            return self.bloom_filter.might_contain(key)
        return True  # Conservative: might be there


class Memtable:
    """In-memory write buffer (like BigTable's memtable)"""

    def __init__(self, max_size: int = 10000):
        self.data: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self.max_size = max_size
        self.lock = threading.Lock()

    def put(self, key: str, record: Dict[str, Any]) -> bool:
        """Add record to memtable"""
        with self.lock:
            self.data[key] = {**record, '_timestamp': time.time()}
            return len(self.data) >= self.max_size

    def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get record from memtable"""
        return self.data.get(key)

    def flush_to_sstable(self, path: Path, columns: List[str]) -> SSTable:
        """Flush memtable to disk as SSTable"""
        with self.lock:
            if not self.data:
                return None

            # Create bloom filter
            bloom = BloomFilter(size=max(10000, len(self.data) * 10))

            # Sort by key for SSTable
            sorted_items = sorted(self.data.items())
            min_key = sorted_items[0][0]
            max_key = sorted_items[-1][0]

            # Write TSV file
            with open(path, 'w') as f:
                # Header
                f.write('\t'.join(columns) + '\n')

                # Data
                for key, record in sorted_items:
                    bloom.add(key)
                    row = [str(record.get(col, '')) for col in columns]
                    f.write('\t'.join(row) + '\n')

            # Save bloom filter
            bloom_path = path.with_suffix('.bloom')
            bloom.save(bloom_path)

            # Clear memtable
            self.data.clear()

            return SSTable(
                path=path,
                min_key=min_key,
                max_key=max_key,
                record_count=len(sorted_items),
                bloom_filter=bloom,
                creation_time=time.time()
            )


class BigTableTSV:
    """
    BigTable-inspired TSV database

    Features:
    - Write to memtable (fast)
    - Flush to SSTables when full
    - Compaction to merge SSTables
    - Bloom filters for fast negatives
    - Sharding by key range
    """

    def __init__(self, table_name: str, columns: List[str],
                 data_dir: Path = None, memtable_size: int = 10000,
                 shard_size: int = 100000):
        self.table_name = table_name
        self.columns = columns
        self.data_dir = data_dir or Path.cwd() / "bigtable_data"
        self.table_dir = self.data_dir / table_name
        self.table_dir.mkdir(parents=True, exist_ok=True)

        # Memtable for writes
        self.memtable = Memtable(memtable_size)
        self.memtable_size = memtable_size

        # SSTables on disk
        self.sstables: List[SSTable] = []
        self._load_sstables()

        # Sharding config
        self.shard_size = shard_size
        self.shards: Dict[str, 'BigTableTSV'] = {}

        # Compaction settings
        self.compaction_threshold = 10  # Compact when we have this many SSTables
        self.last_compaction = time.time()

        # Statistics
        self.stats = {
            'writes': 0,
            'reads': 0,
            'flushes': 0,
            'compactions': 0,
            'bloom_filter_negatives': 0
        }

    def _load_sstables(self):
        """Load existing SSTables from disk"""
        for tsv_file in sorted(self.table_dir.glob("*.tsv")):
            if "compacted" in tsv_file.name:
                continue

            # Load metadata
            meta_file = tsv_file.with_suffix('.meta')
            if meta_file.exists():
                with open(meta_file) as f:
                    meta = json.load(f)

                # Load bloom filter if exists
                bloom_file = tsv_file.with_suffix('.bloom')
                bloom = None
                if bloom_file.exists():
                    bloom = BloomFilter.load(bloom_file)

                sstable = SSTable(
                    path=tsv_file,
                    min_key=meta['min_key'],
                    max_key=meta['max_key'],
                    record_count=meta['record_count'],
                    bloom_filter=bloom,
                    creation_time=meta.get('creation_time', 0),
                    level=meta.get('level', 0)
                )
                self.sstables.append(sstable)

    def insert(self, record: Dict[str, Any]) -> bool:
        """Insert record (goes to memtable first)"""
        key = record.get('id', str(time.time_ns()))

        # Check if we should shard
        shard_id = self._get_shard_id(key)
        if shard_id != "main":
            if shard_id not in self.shards:
                self.shards[shard_id] = BigTableTSV(
                    f"{self.table_name}_shard_{shard_id}",
                    self.columns,
                    self.data_dir
                )
            return self.shards[shard_id].insert(record)

        # Add to memtable
        should_flush = self.memtable.put(key, record)
        self.stats['writes'] += 1

        # Flush if memtable is full
        if should_flush:
            self._flush_memtable()

            # Check if we need compaction
            if len(self.sstables) >= self.compaction_threshold:
                self._compact()

        return True

    def query_one(self, **conditions) -> Optional[Dict[str, Any]]:
        """Query single record (checks memtable then SSTables)"""
        self.stats['reads'] += 1

        if 'id' in conditions:
            key = conditions['id']

            # Check memtable first (newest data)
            result = self.memtable.get(key)
            if result:
                return result

            # Check SSTables (newest to oldest)
            for sstable in reversed(self.sstables):
                # Use bloom filter for quick negative
                if sstable.bloom_filter and not sstable.bloom_filter.might_contain(key):
                    self.stats['bloom_filter_negatives'] += 1
                    continue

                # Check key range
                if not sstable.contains_key_range(key):
                    continue

                # Actually read the SSTable
                result = self._read_from_sstable(sstable, key)
                if result:
                    return result

        # Fallback to scan
        for record in self.query(**conditions):
            return record

        return None

    def _read_from_sstable(self, sstable: SSTable, key: str) -> Optional[Dict[str, Any]]:
        """Read specific key from SSTable using binary search"""
        with open(sstable.path) as f:
            lines = f.readlines()[1:]  # Skip header

            # Binary search since SSTable is sorted
            left, right = 0, len(lines) - 1

            while left <= right:
                mid = (left + right) // 2
                line = lines[mid].strip()
                fields = line.split('\t')

                if len(fields) > 0:
                    record_key = fields[0]  # Assuming first column is ID

                    if record_key == key:
                        # Found it!
                        record = {}
                        for i, col in enumerate(self.columns):
                            if i < len(fields):
                                record[col] = fields[i]
                        return record
                    elif record_key < key:
                        left = mid + 1
                    else:
                        right = mid - 1

        return None

    def _flush_memtable(self):
        """Flush memtable to new SSTable"""
        if not self.memtable.data:
            return

        # Generate SSTable filename
        timestamp = int(time.time() * 1000000)
        sstable_path = self.table_dir / f"sstable_{timestamp}.tsv"

        # Flush to disk
        sstable = self.memtable.flush_to_sstable(sstable_path, self.columns)

        if sstable:
            # Save metadata
            meta_path = sstable_path.with_suffix('.meta')
            with open(meta_path, 'w') as f:
                json.dump({
                    'min_key': sstable.min_key,
                    'max_key': sstable.max_key,
                    'record_count': sstable.record_count,
                    'creation_time': sstable.creation_time,
                    'level': 0
                }, f)

            self.sstables.append(sstable)
            self.stats['flushes'] += 1

    def _compact(self):
        """Merge multiple SSTables into one (like BigTable compaction)"""
        if len(self.sstables) < 2:
            return

        print(f"🔄 Compacting {len(self.sstables)} SSTables...")

        # Simple size-tiered compaction strategy
        # Merge all SSTables at the same level
        levels = defaultdict(list)
        for sstable in self.sstables:
            levels[sstable.level].append(sstable)

        # Compact level 0 (newest data)
        if len(levels[0]) >= self.compaction_threshold:
            self._merge_sstables(levels[0], new_level=1)
            self.stats['compactions'] += 1

    def _merge_sstables(self, sstables: List[SSTable], new_level: int):
        """Merge multiple SSTables into one larger SSTable"""
        # Collect all records
        all_records = {}

        for sstable in sstables:
            with open(sstable.path) as f:
                header = f.readline().strip().split('\t')
                for line in f:
                    fields = line.strip().split('\t')
                    if fields:
                        key = fields[0]
                        record = {col: fields[i] if i < len(fields) else ''
                                for i, col in enumerate(header)}
                        # Newer data overwrites older
                        all_records[key] = record

        if not all_records:
            return

        # Write merged SSTable
        timestamp = int(time.time() * 1000000)
        merged_path = self.table_dir / f"compacted_{new_level}_{timestamp}.tsv"

        # Sort by key
        sorted_items = sorted(all_records.items())
        min_key = sorted_items[0][0]
        max_key = sorted_items[-1][0]

        # Create new bloom filter
        bloom = BloomFilter(size=max(10000, len(sorted_items) * 10))

        # Write merged data
        with open(merged_path, 'w') as f:
            f.write('\t'.join(self.columns) + '\n')
            for key, record in sorted_items:
                bloom.add(key)
                row = [str(record.get(col, '')) for col in self.columns]
                f.write('\t'.join(row) + '\n')

        # Save bloom filter
        bloom.save(merged_path.with_suffix('.bloom'))

        # Save metadata
        with open(merged_path.with_suffix('.meta'), 'w') as f:
            json.dump({
                'min_key': min_key,
                'max_key': max_key,
                'record_count': len(sorted_items),
                'creation_time': time.time(),
                'level': new_level
            }, f)

        # Create new SSTable
        new_sstable = SSTable(
            path=merged_path,
            min_key=min_key,
            max_key=max_key,
            record_count=len(sorted_items),
            bloom_filter=bloom,
            creation_time=time.time(),
            level=new_level
        )

        # Remove old SSTables
        for sstable in sstables:
            self.sstables.remove(sstable)
            # Delete old files
            sstable.path.unlink(missing_ok=True)
            sstable.path.with_suffix('.meta').unlink(missing_ok=True)
            sstable.path.with_suffix('.bloom').unlink(missing_ok=True)

        # Add new compacted SSTable
        self.sstables.append(new_sstable)

        print(f"✅ Compacted {len(sstables)} SSTables → 1 SSTable at level {new_level}")

    def _get_shard_id(self, key: str) -> str:
        """Determine shard for key"""
        # Simple hash-based sharding
        if len(self.memtable.data) + sum(s.record_count for s in self.sstables) < self.shard_size:
            return "main"

        # Hash key to determine shard
        key_hash = hashlib.md5(key.encode()).digest()
        shard_num = struct.unpack('I', key_hash[:4])[0] % 10
        return str(shard_num)

    def get_stats(self) -> Dict[str, Any]:
        """Get database statistics"""
        return {
            **self.stats,
            'memtable_size': len(self.memtable.data),
            'sstable_count': len(self.sstables),
            'total_records': sum(s.record_count for s in self.sstables) + len(self.memtable.data),
            'shard_count': len(self.shards),
            'sstable_levels': list(set(s.level for s in self.sstables))
        }

    def query(self, **conditions) -> Iterator[Dict[str, Any]]:
        """Query all matching records"""
        # Check memtable
        for key, record in self.memtable.data.items():
            if all(record.get(k) == v for k, v in conditions.items()):
                yield record

        # Check SSTables
        for sstable in reversed(self.sstables):  # Newest first
            with open(sstable.path) as f:
                header = f.readline().strip().split('\t')
                for line in f:
                    fields = line.strip().split('\t')
                    if fields:
                        record = {col: fields[i] if i < len(fields) else ''
                                for i, col in enumerate(header)}
                        if all(record.get(k) == v for k, v in conditions.items()):
                            yield record


def demo_bigtable_tsv():
    """Demonstrate BigTable-inspired features"""
    print("=" * 60)
    print("BigTable-Inspired TSV Database Demo")
    print("=" * 60)

    # Create database
    db = BigTableTSV("users", ["id", "name", "email", "age"])

    print("\n1. Testing Memtable → SSTable flow:")
    print("-" * 40)

    # Insert data (goes to memtable)
    for i in range(25000):
        db.insert({
            "id": str(i),
            "name": f"User_{i}",
            "email": f"user{i}@example.com",
            "age": str(20 + (i % 50))
        })

        if i % 5000 == 0:
            stats = db.get_stats()
            print(f"  After {i:,} inserts:")
            print(f"    Memtable: {stats['memtable_size']:,} records")
            print(f"    SSTables: {stats['sstable_count']} files")
            print(f"    Flushes: {stats['flushes']}")
            print(f"    Compactions: {stats['compactions']}")

    # Force final flush
    db._flush_memtable()

    final_stats = db.get_stats()
    print(f"\n2. Final Statistics:")
    print(f"  Total records: {final_stats['total_records']:,}")
    print(f"  SSTables: {final_stats['sstable_count']}")
    print(f"  Levels: {final_stats['sstable_levels']}")
    print(f"  Bloom filter negatives: {final_stats['bloom_filter_negatives']}")

    print("\n3. Testing Query Performance:")
    print("-" * 40)

    # Query with bloom filters
    import time

    start = time.perf_counter()
    for i in range(100):
        result = db.query_one(id=str(i * 250))
    elapsed = time.perf_counter() - start

    print(f"  100 queries in {elapsed:.3f}s ({100/elapsed:.0f} queries/sec)")
    print(f"  Bloom filter saved {final_stats['bloom_filter_negatives']} disk reads!")

    print("\n✅ BigTable concepts successfully implemented with TSV!")


if __name__ == "__main__":
    demo_bigtable_tsv()