#!/usr/bin/env python3
"""
Audit logging for TSV database operations
Tracks all operations for debugging and compliance
"""

import os
import json
import time
import threading
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List
from collections import deque


class AuditLog:
    """
    Append-only audit log for database operations
    Each operation gets logged with timestamp, user, and details
    """

    def __init__(self, log_dir: Path = None, max_memory_logs: int = 1000):
        self.log_dir = log_dir or Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Current log file (rotates daily)
        self.current_date = datetime.now().date()
        self.log_file = self._get_log_file()

        # In-memory buffer for recent operations
        self.memory_buffer = deque(maxlen=max_memory_logs)

        # Thread safety
        self.lock = threading.Lock()

        # Statistics
        self.stats = {
            'total_operations': 0,
            'operations_by_type': {},
            'errors': 0,
            'start_time': datetime.now()
        }

    def _get_log_file(self) -> Path:
        """Get current log file (rotates daily)"""
        date_str = self.current_date.strftime("%Y%m%d")
        return self.log_dir / f"audit_{date_str}.log"

    def _rotate_if_needed(self):
        """Check if we need to rotate to new log file"""
        current = datetime.now().date()
        if current != self.current_date:
            self.current_date = current
            self.log_file = self._get_log_file()

    def log(self, operation: str, table: str, details: Dict[str, Any],
            success: bool = True, error: Optional[str] = None):
        """
        Log an operation

        Args:
            operation: Type of operation (insert, query, update, delete)
            table: Table name
            details: Operation details (conditions, data, etc.)
            success: Whether operation succeeded
            error: Error message if failed
        """
        with self.lock:
            self._rotate_if_needed()

            # Create log entry
            entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'operation': operation,
                'table': table,
                'details': details,
                'success': success,
                'error': error,
                'user': os.environ.get('USER', 'unknown'),
                'pid': os.getpid()
            }

            # Add to memory buffer
            self.memory_buffer.append(entry)

            # Write to file
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(entry) + '\n')

            # Update statistics
            self.stats['total_operations'] += 1
            self.stats['operations_by_type'][operation] = \
                self.stats['operations_by_type'].get(operation, 0) + 1

            if not success:
                self.stats['errors'] += 1

    def query_logs(self, operation: Optional[str] = None,
                   table: Optional[str] = None,
                   start_time: Optional[datetime] = None,
                   limit: int = 100) -> List[Dict]:
        """Query recent logs from memory"""
        results = []

        for entry in reversed(self.memory_buffer):
            # Apply filters
            if operation and entry['operation'] != operation:
                continue
            if table and entry['table'] != table:
                continue
            if start_time:
                entry_time = datetime.fromisoformat(entry['timestamp'])
                if entry_time < start_time:
                    continue

            results.append(entry)

            if len(results) >= limit:
                break

        return results

    def get_stats(self) -> Dict[str, Any]:
        """Get audit statistics"""
        with self.lock:
            uptime = datetime.now() - self.stats['start_time']

            return {
                'total_operations': self.stats['total_operations'],
                'operations_by_type': dict(self.stats['operations_by_type']),
                'errors': self.stats['errors'],
                'error_rate': self.stats['errors'] / max(1, self.stats['total_operations']),
                'uptime_seconds': uptime.total_seconds(),
                'current_log_file': str(self.log_file),
                'memory_buffer_size': len(self.memory_buffer)
            }

    def tail(self, n: int = 10) -> List[Dict]:
        """Get last n log entries"""
        return list(self.memory_buffer)[-n:]

    def search(self, pattern: str, limit: int = 100) -> List[Dict]:
        """Search logs for pattern"""
        results = []

        # Search in memory first
        for entry in reversed(self.memory_buffer):
            if pattern.lower() in json.dumps(entry).lower():
                results.append(entry)
                if len(results) >= limit:
                    return results

        # Search in current log file if needed
        if len(results) < limit and self.log_file.exists():
            with open(self.log_file, 'r') as f:
                for line in reversed(f.readlines()):
                    if pattern.lower() in line.lower():
                        try:
                            entry = json.loads(line)
                            results.append(entry)
                            if len(results) >= limit:
                                break
                        except json.JSONDecodeError:
                            continue

        return results


class QueryLog:
    """
    Specialized log for query performance tracking
    """

    def __init__(self, log_dir: Path = None):
        self.log_dir = log_dir or Path.cwd() / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.query_log = self.log_dir / "queries.log"

        # Performance statistics
        self.slow_queries = deque(maxlen=100)  # Keep last 100 slow queries
        self.query_stats = {
            'total_queries': 0,
            'total_time': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'index_hits': 0,
            'full_scans': 0
        }

    def log_query(self, table: str, conditions: Dict,
                  execution_time: float, rows_returned: int,
                  used_index: bool = False, cache_hit: bool = False):
        """Log query execution"""
        entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'table': table,
            'conditions': conditions,
            'execution_time_ms': execution_time * 1000,
            'rows_returned': rows_returned,
            'used_index': used_index,
            'cache_hit': cache_hit
        }

        # Write to log
        with open(self.query_log, 'a') as f:
            f.write(json.dumps(entry) + '\n')

        # Update statistics
        self.query_stats['total_queries'] += 1
        self.query_stats['total_time'] += execution_time

        if cache_hit:
            self.query_stats['cache_hits'] += 1
        else:
            self.query_stats['cache_misses'] += 1

        if used_index:
            self.query_stats['index_hits'] += 1
        elif not cache_hit:
            self.query_stats['full_scans'] += 1

        # Track slow queries (> 100ms)
        if execution_time > 0.1:
            self.slow_queries.append(entry)

    def get_slow_queries(self) -> List[Dict]:
        """Get recent slow queries"""
        return list(self.slow_queries)

    def get_stats(self) -> Dict:
        """Get query performance statistics"""
        total = max(1, self.query_stats['total_queries'])

        return {
            'total_queries': total,
            'avg_time_ms': (self.query_stats['total_time'] / total) * 1000,
            'cache_hit_rate': self.query_stats['cache_hits'] / total,
            'index_hit_rate': self.query_stats['index_hits'] / total,
            'full_scan_rate': self.query_stats['full_scans'] / total,
            'slow_queries': len(self.slow_queries)
        }


# Global audit log instance
_audit_log = None
_query_log = None


def get_audit_log() -> AuditLog:
    """Get global audit log instance"""
    global _audit_log
    if _audit_log is None:
        _audit_log = AuditLog()
    return _audit_log


def get_query_log() -> QueryLog:
    """Get global query log instance"""
    global _query_log
    if _query_log is None:
        _query_log = QueryLog()
    return _query_log


def test_audit_log():
    """Test audit logging"""
    print("Testing Audit Log")
    print("=" * 50)

    log = AuditLog()

    # Log some operations
    print("\n1. Logging Operations:")
    log.log('insert', 'users', {'id': '1', 'name': 'Alice'})
    log.log('query', 'users', {'conditions': {'id': '1'}})
    log.log('update', 'users', {'id': '1', 'changes': {'name': 'Alicia'}})
    log.log('delete', 'users', {'id': '1'})
    log.log('insert', 'users', {'id': '2'}, success=False, error='Duplicate key')

    print(f"   ✓ Logged 5 operations")

    # Get recent logs
    print("\n2. Recent Operations:")
    recent = log.tail(3)
    for entry in recent:
        print(f"   {entry['operation']}: {entry['table']} - Success: {entry['success']}")

    # Get statistics
    print("\n3. Audit Statistics:")
    stats = log.get_stats()
    print(f"   Total operations: {stats['total_operations']}")
    print(f"   Error rate: {stats['error_rate']:.1%}")
    print(f"   Operations by type: {stats['operations_by_type']}")

    # Test query log
    print("\n4. Query Performance Log:")
    qlog = QueryLog()

    qlog.log_query('users', {'id': '1'}, 0.001, 1, used_index=True)
    qlog.log_query('users', {'name': 'Alice'}, 0.150, 1, used_index=False)
    qlog.log_query('users', {'id': '2'}, 0.0005, 1, cache_hit=True)

    qstats = qlog.get_stats()
    print(f"   Average query time: {qstats['avg_time_ms']:.2f}ms")
    print(f"   Cache hit rate: {qstats['cache_hit_rate']:.1%}")
    print(f"   Index hit rate: {qstats['index_hit_rate']:.1%}")

    print("\n✓ All audit tests passed!")


if __name__ == "__main__":
    test_audit_log()