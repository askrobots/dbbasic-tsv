#!/usr/bin/env python3
"""
Basic tests for dbbasic-tsv
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from dbbasic import TSV


class TestBasicOperations(unittest.TestCase):
    """Test basic CRUD operations"""

    def setUp(self):
        """Create temporary directory and test table"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))
        self.db = TSV("test_users", ["id", "name", "email"], data_dir=self.test_dir)

    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_insert_single(self):
        """Test single record insertion"""
        result = self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        self.assertTrue(result)
        self.assertEqual(self.db.count(), 1)

    def test_insert_many(self):
        """Test batch insertion"""
        records = [
            {"id": "1", "name": "Alice", "email": "alice@example.com"},
            {"id": "2", "name": "Bob", "email": "bob@example.com"},
            {"id": "3", "name": "Charlie", "email": "charlie@example.com"},
        ]
        count = self.db.insert_many(records)
        self.assertEqual(count, 3)
        self.assertEqual(self.db.count(), 3)

    def test_query(self):
        """Test querying records"""
        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        self.db.insert({"id": "2", "name": "Bob", "email": "bob@example.com"})

        # Query by ID
        results = self.db.query(id="1")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["name"], "Alice")

        # Query all
        results = self.db.query()
        self.assertEqual(len(results), 2)

    def test_query_one(self):
        """Test querying single record"""
        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})

        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Alice")

        # Non-existent record
        result = self.db.query_one(id="999")
        self.assertIsNone(result)

    def test_update(self):
        """Test updating records"""
        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})

        updated = self.db.update({"id": "1"}, {"email": "newalice@example.com"})
        self.assertEqual(updated, 1)

        result = self.db.query_one(id="1")
        self.assertEqual(result["email"], "newalice@example.com")

    def test_delete(self):
        """Test deleting records"""
        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        self.db.insert({"id": "2", "name": "Bob", "email": "bob@example.com"})

        deleted = self.db.delete(id="1")
        self.assertEqual(deleted, 1)
        self.assertEqual(self.db.count(), 1)

        # Verify correct record was deleted
        result = self.db.query_one(id="2")
        self.assertIsNotNone(result)
        self.assertEqual(result["name"], "Bob")

    def test_count(self):
        """Test counting records"""
        self.assertEqual(self.db.count(), 0)

        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        self.assertEqual(self.db.count(), 1)

        self.db.insert({"id": "2", "name": "Bob", "email": "bob@example.com"})
        self.assertEqual(self.db.count(), 2)

        # Count with conditions
        self.assertEqual(self.db.count(name="Alice"), 1)

    def test_all(self):
        """Test getting all records"""
        records = [
            {"id": str(i), "name": f"User{i}", "email": f"user{i}@example.com"}
            for i in range(5)
        ]
        self.db.insert_many(records)

        all_records = list(self.db.all())
        self.assertEqual(len(all_records), 5)

    def test_truncate(self):
        """Test truncating table"""
        self.db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        self.db.insert({"id": "2", "name": "Bob", "email": "bob@example.com"})

        self.db.truncate()
        self.assertEqual(self.db.count(), 0)

        # Table should still be usable
        self.db.insert({"id": "3", "name": "Charlie", "email": "charlie@example.com"})
        self.assertEqual(self.db.count(), 1)


class TestIndexing(unittest.TestCase):
    """Test indexing functionality"""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))
        self.db = TSV("test_indexed", ["id", "email", "status"], data_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_primary_key_index(self):
        """Test that primary key is automatically indexed"""
        # Insert test data
        for i in range(100):
            self.db.insert({"id": str(i), "email": f"user{i}@example.com", "status": "active"})

        # Query by ID should use index (fast)
        import time
        start = time.perf_counter()
        result = self.db.query_one(id="50")
        elapsed = time.perf_counter() - start

        self.assertIsNotNone(result)
        self.assertLess(elapsed, 0.01)  # Should be very fast with index

    def test_create_custom_index(self):
        """Test creating custom index"""
        # Insert test data
        for i in range(100):
            self.db.insert({"id": str(i), "email": f"user{i}@example.com", "status": "active"})

        # Create index on email
        self.db.create_index("email")

        # Query by email should now be fast
        result = self.db.query_one(email="user50@example.com")
        self.assertIsNotNone(result)
        self.assertEqual(result["id"], "50")


class TestTransactions(unittest.TestCase):
    """Test transaction support"""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))
        self.db = TSV("test_tx", ["id", "value"], data_dir=self.test_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_successful_transaction(self):
        """Test successful transaction commit"""
        self.db.insert({"id": "1", "value": "100"})
        self.db.insert({"id": "2", "value": "200"})

        with self.db.transaction() as tx:
            tx.update({"id": "1"}, {"value": "150"})
            tx.update({"id": "2"}, {"value": "250"})

        # Check values were updated
        self.assertEqual(self.db.query_one(id="1")["value"], "150")
        self.assertEqual(self.db.query_one(id="2")["value"], "250")

    def test_transaction_rollback(self):
        """Test transaction rollback on error"""
        self.db.insert({"id": "1", "value": "100"})

        try:
            with self.db.transaction() as tx:
                tx.update({"id": "1"}, {"value": "200"})
                raise Exception("Simulated error")
        except Exception:
            pass

        # Value should not have changed
        self.assertEqual(self.db.query_one(id="1")["value"], "100")


if __name__ == "__main__":
    unittest.main()