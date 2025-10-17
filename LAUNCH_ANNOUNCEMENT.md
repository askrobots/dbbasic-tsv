# dbbasic-tsv Launch Announcement

## We Just Published Our Database to PyPI

**Date:** September 29, 2025
**Package:** dbbasic-tsv v1.0.1
**Status:** Live in production on quellhorst.com

### What We Built

A pure-Python, zero-dependency database that stores data in human-readable TSV (tab-separated values) files. No PostgreSQL, no Redis, no SQLite - just text files you can grep, edit in vim, and commit to git.

### The Story

While building our YouTube-like video platform, we started with the usual "proper" database setup. Then we realized we were overengineering. We tried storing data in JSON files with Python data structures. That worked, but felt clunky.

So we built dbbasic-tsv - a database that treats TSV files as first-class citizens with proper indexing, transactions, and concurrent access. Turns out, text files + smart indexing = surprisingly fast.

### Real-World Performance

**Pure Python (what we're using):**
- 163,000 inserts/second
- 93 queries/second on 10K records
- Zero dependencies
- Works everywhere

**With optional Rust acceleration:**
- 600,000+ inserts/second
- 88,000 queries/second
- Still zero runtime dependencies

For comparison, SQLite does ~713K inserts/sec and 126K queries/sec. We're in the ballpark for 95% of use cases.

### Why This Matters

**Human-Readable:**
```bash
$ cat data/posts.tsv
id      title                   slug            date
1       Hello World            hello-world     2025-09-29
2       Second Post            second-post     2025-09-30
```

You can literally grep your database:
```bash
$ grep "Hello World" data/posts.tsv
1       Hello World            hello-world     2025-09-29
```

**Git-Friendly:**
```bash
$ git diff data/posts.tsv
+3      Third Post             third-post      2025-10-01
```

See exactly what changed. Meaningful diffs. No binary blobs.

**Zero Setup:**
```python
from dbbasic.tsv import TSV

posts = TSV("posts", ["id", "title", "slug", "date"])
posts.insert({"id": "1", "title": "Hello World", "slug": "hello-world", "date": "2025-09-29"})

post = posts.query_one(slug="hello-world")
```

That's it. No migrations, no connection strings, no docker-compose.

### Now Live on quellhorst.com

We just migrated quellhorst.com from JSON files + Python data structures to dbbasic-tsv. The migration took minutes. The site is faster. The code is cleaner. We can grep the database.

**Before (Flask + JSON):**
```python
# Load entire JSON file into memory
with open('posts.json') as f:
    posts = json.load(f)

# Manual filtering
post = next(p for p in posts if p['slug'] == slug)

# Save entire structure back
with open('posts.json', 'w') as f:
    json.dump(posts, f)
```

**After (dbbasic-tsv):**
```python
posts = TSV("posts", ["id", "title", "slug", "date", "content"])
post = posts.query_one(slug=slug)
posts.update({"slug": slug}, {"views": post["views"] + 1})
```

Indexes handle lookups. Transactions handle atomicity. Locking handles concurrency. It just works.

### What We Learned

1. **Text files aren't slow** - With proper indexing, they're fast enough for 95% of use cases
2. **Simplicity compounds** - No database server means no ops, no backups, no connection pools
3. **Debuggability matters** - Being able to grep your database is a superpower
4. **Git is a database** - Version control for data is incredibly powerful
5. **Zero dependencies wins** - Pure Python means it runs everywhere

### The Architecture

Inspired by Google BigTable:
- **Append-only writes** - Fast and corruption-resistant
- **In-memory indexes** - Built on startup, updated on writes
- **Memtable pattern** - Hot data in memory, cold data on disk
- **Compaction** - Periodic cleanup of deleted records
- **Bloom filters** - Fast negative lookups (coming soon)

Plus file-based locking for concurrent access and full ACID transactions with rollback.

### Try It Yourself

```bash
pip install dbbasic-tsv
```

Full docs: https://github.com/askrobots/dbbasic-tsv

### When to Use This

✅ **Perfect for:**
- Prototypes and MVPs
- Microservices (no dependencies!)
- Config and settings storage
- Audit logs (human-readable!)
- Data that needs version control
- Embedded systems
- Side projects like blogs

❌ **Not ideal for:**
- Complex JOINs
- Massive datasets (>10GB)
- High-frequency trading
- When you actually need PostgreSQL

### The Philosophy

> "If you can't grep it, you don't own it."

We believe in:
- **Simplicity over features** - Do one thing well
- **Text over binary** - Human-readable always wins
- **Zero setup over configuration** - It should just work
- **Optional complexity** - Start simple, optimize later

### What's Next

- Blog post with migration details
- Performance benchmarks vs PostgreSQL
- Video demo showing the grep workflow
- Integration examples for Flask/FastAPI
- Maybe a Show HN post?

### Credits

Built by the AskRobots team while building a video platform and discovering we didn't need "real" databases for 90% of our use cases.

Special thanks to:
- Google BigTable for the architectural inspiration
- The Unix philosophy for reminding us that text streams are powerful
- The Rust community for showing us how to make Python fast
- Every developer who's over-engineered a database setup (we've been there)

---

**Remember:** The best database is the one you don't have to set up.

Package: https://pypi.org/project/dbbasic-tsv/
Source: https://github.com/askrobots/dbbasic-tsv
License: MIT