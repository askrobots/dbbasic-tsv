#!/usr/bin/env python3
"""
Edge case tests for dbbasic-tsv
"""

import unittest
import tempfile
import shutil
from pathlib import Path
from dbbasic import TSV


class TestEdgeCases(unittest.TestCase):
    """Test edge cases and boundary conditions"""

    def setUp(self):
        """Create temporary directory and test table"""
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))
        self.db = TSV("test_edge", ["id", "data", "value"], data_dir=self.test_dir)

    def tearDown(self):
        """Clean up test directory"""
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_empty_strings(self):
        """Test handling of empty string values"""
        self.db.insert({"id": "1", "data": "", "value": ""})
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "")
        self.assertEqual(result["value"], "")

    def test_special_characters(self):
        """Test handling of special characters"""
        special_data = "Hello\nWorld\tTest\"Quote'Single"
        self.db.insert({"id": "1", "data": special_data, "value": "test"})
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        # Data should be preserved (though newlines/tabs may be escaped)
        self.assertIn("Hello", result["data"])

    def test_unicode_characters(self):
        """Test handling of Unicode/emoji characters"""
        unicode_data = "Hello 世界 🎉 café"
        self.db.insert({"id": "1", "data": unicode_data, "value": "test"})
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], unicode_data)

    def test_very_long_strings(self):
        """Test handling of very long strings"""
        long_data = "x" * 10000
        self.db.insert({"id": "1", "data": long_data, "value": "test"})
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        self.assertEqual(len(result["data"]), 10000)

    def test_missing_columns(self):
        """Test inserting record with missing columns"""
        self.db.insert({"id": "1", "data": "test"})  # missing 'value'
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        self.assertEqual(result["data"], "test")
        self.assertEqual(result.get("value", ""), "")

    def test_extra_columns(self):
        """Test inserting record with extra columns"""
        self.db.insert({"id": "1", "data": "test", "value": "val", "extra": "ignored"})
        result = self.db.query_one(id="1")
        self.assertIsNotNone(result)
        # Extra column should be ignored
        self.assertNotIn("extra", result)

    def test_duplicate_ids(self):
        """Test handling of duplicate IDs"""
        self.db.insert({"id": "1", "data": "first", "value": "100"})
        self.db.insert({"id": "1", "data": "second", "value": "200"})

        results = self.db.query(id="1")
        # Both records should exist (TSV doesn't enforce uniqueness by default)
        self.assertEqual(len(results), 2)

    def test_query_nonexistent_field(self):
        """Test querying with non-existent field"""
        self.db.insert({"id": "1", "data": "test", "value": "100"})
        results = self.db.query(nonexistent="value")
        # Should return empty results, not error
        self.assertEqual(len(results), 0)

    def test_update_nonexistent_record(self):
        """Test updating non-existent record"""
        updated = self.db.update({"id": "999"}, {"data": "new"})
        self.assertEqual(updated, 0)

    def test_delete_nonexistent_record(self):
        """Test deleting non-existent record"""
        deleted = self.db.delete(id="999")
        self.assertEqual(deleted, 0)

    def test_empty_database_operations(self):
        """Test operations on empty database"""
        self.assertEqual(self.db.count(), 0)
        self.assertEqual(len(self.db.query(id="1")), 0)
        self.assertIsNone(self.db.query_one(id="1"))
        self.assertEqual(list(self.db.all()), [])

    def test_large_batch_insert(self):
        """Test inserting large batch of records"""
        records = [
            {"id": str(i), "data": f"data_{i}", "value": str(i * 10)}
            for i in range(1000)
        ]
        count = self.db.insert_many(records)
        self.assertEqual(count, 1000)
        self.assertEqual(self.db.count(), 1000)

    def test_multiple_queries_same_condition(self):
        """Test multiple queries with same condition"""
        for i in range(10):
            self.db.insert({"id": str(i), "data": "active", "value": str(i)})

        results = self.db.query(data="active")
        self.assertEqual(len(results), 10)

    def test_update_multiple_records(self):
        """Test updating multiple records at once"""
        for i in range(5):
            self.db.insert({"id": str(i), "data": "old", "value": str(i)})

        updated = self.db.update({"data": "old"}, {"data": "new"})
        self.assertEqual(updated, 5)

        results = self.db.query(data="new")
        self.assertEqual(len(results), 5)

    def test_delete_multiple_records(self):
        """Test deleting multiple records at once"""
        for i in range(5):
            self.db.insert({"id": str(i), "data": "delete_me", "value": str(i)})

        deleted = self.db.delete(data="delete_me")
        self.assertEqual(deleted, 5)
        self.assertEqual(self.db.count(), 0)


class TestDataIntegrity(unittest.TestCase):
    """Test data integrity and persistence"""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_persistence_across_instances(self):
        """Test that data persists when reopening database"""
        # Create database and insert data
        db1 = TSV("persist_test", ["id", "name"], data_dir=self.test_dir)
        db1.insert({"id": "1", "name": "Alice"})
        db1.insert({"id": "2", "name": "Bob"})
        del db1

        # Reopen database in same directory
        db2 = TSV("persist_test", ["id", "name"], data_dir=self.test_dir)
        self.assertEqual(db2.count(), 2)
        result = db2.query_one(id="1")
        self.assertEqual(result["name"], "Alice")

    def test_index_rebuild_on_load(self):
        """Test that indexes are rebuilt when loading existing data"""
        # Create database with data
        db1 = TSV("index_test", ["id", "email"], data_dir=self.test_dir)
        for i in range(100):
            db1.insert({"id": str(i), "email": f"user{i}@example.com"})
        del db1

        # Reopen and verify index works
        db2 = TSV("index_test", ["id", "email"], data_dir=self.test_dir)
        result = db2.query_one(id="50")
        self.assertIsNotNone(result)
        self.assertEqual(result["email"], "user50@example.com")

    def test_data_file_format(self):
        """Test that data file is valid TSV format"""
        db = TSV("format_test", ["id", "name", "email"], data_dir=self.test_dir)
        db.insert({"id": "1", "name": "Alice", "email": "alice@example.com"})
        db.insert({"id": "2", "name": "Bob", "email": "bob@example.com"})

        # Read file directly and verify TSV format
        data_file = self.test_dir / "format_test.tsv"
        with open(data_file) as f:
            lines = f.readlines()

        # First line should be header
        self.assertEqual(lines[0].strip(), "id\tname\temail")

        # Data lines should have tab separators
        self.assertIn("\t", lines[1])
        self.assertIn("\t", lines[2])


class TestErrorHandling(unittest.TestCase):
    """Test error handling"""

    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp(prefix="dbbasic_test_"))

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_create_index_invalid_column(self):
        """Test creating index on non-existent column raises error"""
        db = TSV("error_test", ["id", "name"], data_dir=self.test_dir)
        with self.assertRaises(ValueError):
            db.create_index("nonexistent_column")

    def test_transaction_preserves_data_on_error(self):
        """Test that transaction errors don't corrupt data"""
        db = TSV("tx_error_test", ["id", "value"], data_dir=self.test_dir)
        db.insert({"id": "1", "value": "100"})
        db.insert({"id": "2", "value": "200"})

        original_count = db.count()

        try:
            with db.transaction() as tx:
                tx.update({"id": "1"}, {"value": "999"})
                tx.delete(id="2")
                raise Exception("Test error")
        except:
            pass

        # Database should still have original records
        self.assertEqual(db.count(), original_count)
        self.assertEqual(db.query_one(id="1")["value"], "100")
        self.assertIsNotNone(db.query_one(id="2"))


if __name__ == "__main__":
    unittest.main()