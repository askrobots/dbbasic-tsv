# Changelog

All notable changes to dbbasic-tsv will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.1] - 2025-09-29

### Changed
- Updated author attribution from "TubeKit Contributors" to "AskRobots Contributors"
- Updated README to reflect AskRobots branding

## [1.0.0] - 2025-09-29

### Added
- Initial public release
- Core TSV database functionality
- CRUD operations (Create, Read, Update, Delete)
- Transaction support with rollback
- File-based locking for concurrent access
- In-memory indexing on first column
- Human-readable TSV file format
- Optional Rust acceleration for performance
- `create_index()` method for explicit index management
- `transaction()` context manager for atomic operations
- `query()` and `query_one()` methods for data retrieval
- `insert()`, `insert_many()` for adding records
- `update()` and `delete()` for modifying data
- `truncate()` and `drop()` for table management
- `backup()` and `restore()` for data safety
- `stats()` method for table statistics
- BigTable-inspired architecture
- Audit logging support
- Comprehensive test suite (13 tests)
- Examples and benchmarks
- Full documentation

### Performance
- Pure Python: 197K inserts/sec, 90 queries/sec
- Rust accelerated: 600K inserts/sec, 88K queries/sec
- Zero dependencies for core functionality

### Documentation
- Complete README with examples
- API documentation
- Contributing guidelines
- Philosophy and design principles

## [Unreleased]

### Planned
- Distributed sharding
- Real-time file watchers
- GraphQL API generation
- WASM compilation
- Compression support
- Encryption at rest
- S3 backend option

---

[1.0.1]: https://github.com/askrobots/dbbasic-tsv/releases/tag/v1.0.1
[1.0.0]: https://github.com/askrobots/dbbasic-tsv/releases/tag/v1.0.0