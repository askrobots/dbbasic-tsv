# Architecture Philosophy

## The Accidental Document Database

While building dbbasic-tsv, we accidentally discovered something profound: **Git IS a database for certain types of data.**

### The Key Insight

Most document databases (MongoDB, CouchDB) tried to add version control features to databases:
- Complex replication protocols
- Conflict resolution strategies
- Version history bolted on
- Operational complexity

**We're doing the opposite: Adding database features to Git.**

| Database Feature | Traditional Approach | dbbasic-tsv + Git |
|-----------------|---------------------|-------------------|
| Replication | Complex cluster setup | `git push` |
| Backup | mongodump, pg_dump | `git clone` |
| Version History | Limited or expensive | `git log` (full history) |
| Rollback | Complex procedures | `git revert` |
| Diff changes | Special tools | `git diff` |
| Branching | Not supported | `git branch` (test environments) |
| Read data | Need client library | `cat data.tsv` |
| Ops complexity | High | Zero |

## The One-Way Database

dbbasic-tsv excels at **one-way data flow** scenarios:

```
Development → Production (via git push)
```

This works perfectly for:
- Blog posts and articles
- Documentation
- Product catalogs
- Configuration
- Marketing pages
- Static content

**Why it works:** Your deployment pipeline IS your database replication.

```bash
# Development
vim data/articles.tsv
git add .
git commit -m "New article"
git push

# Production (Docker/server)
git pull  # Database updated!
```

### Docker Containers: Perfect Match

For Docker containers **without persistent volumes**, dbbasic-tsv is ideal:
- Container starts → pulls latest git repo → has fresh database
- Container restarts → same data every time
- No volume mounts needed
- No database containers to orchestrate

```dockerfile
FROM python:3.11-slim
RUN pip install dbbasic-tsv
RUN git clone https://github.com/yourorg/content-data.git /data
CMD ["python", "app.py"]  # Reads from /data/*.tsv
```

## When It Breaks: Bidirectional Data Flow

dbbasic-tsv is **NOT suitable** when production generates data that needs to flow back:

```
Development ←→ Production  # This doesn't work!
```

### The E-Commerce Problem

```python
# Customer 1 buys item → TSV updated → git commit → git push
# Customer 2 buys item → TSV updated → git commit → git pull? CONFLICT!
```

When you have:
- High write concurrency (many writers)
- Transactional requirements (orders must not be lost)
- Real-time inventory (prevent overselling)
- User-generated content (comments, reviews)

**You need a real database** (PostgreSQL, etc.) for:
- Row-level locking
- ACID guarantees
- Concurrent writes
- No merge conflicts

## The Hybrid Architecture

Most applications need **both** types of data:

```
Content/Configuration          Transactional Data
(Infrequent writes)           (Frequent writes)
(One author at a time)        (Concurrent writers)
(History matters)             (Current state matters)
        ↓                             ↓
   dbbasic-tsv                   PostgreSQL
    + Git                      (ACID, locking)
```

### Real-World Example

```python
# Content: Git + TSV (served from git repo)
from dbbasic.tsv import TSV
articles = TSV("articles")  # Blog posts, pages
products = TSV("products")  # Product catalog (descriptions, images)
config = TSV("config")      # App configuration

# Transactions: PostgreSQL (real database)
import psycopg2
orders_db = psycopg2.connect(...)  # Shopping carts, orders
users_db = psycopg2.connect(...)   # User accounts, sessions
inventory_db = psycopg2.connect(...)  # Real-time inventory
```

### The WordPress Mistake

WordPress uses MySQL for **everything**:
- ❌ Pages (don't need transactions)
- ❌ Posts (don't need transactions)
- ❌ Media (don't need transactions)
- ❌ Settings (don't need transactions)
- ✅ Comments (need concurrency)

Result: 80% of WordPress sites run MySQL for one feature (comments), and most disable comments anyway!

**Better approach:**
- Static pages/posts: TSV + Git (no database needed)
- Comments only: Tiny PostgreSQL instance or third-party service
- Massive cost/complexity reduction

## Document Store Vision

dbbasic-tsv could become a real document database for content management:

```python
from dbbasic_tsv import DocumentStore

# Initialize
docs = DocumentStore("articles", data_dir="data")

# Insert - just a dict, stored as JSON in TSV
docs.insert({
    "slug": "my-article",
    "title": "Hello World",
    "content": {"blocks": [...]},  # Rich JSON structure
    "tags": ["python", "web"],
    "metadata": {"author": "alice", "date": "2024-01-01"}
})

# Query - simple Python (no query language!)
results = docs.find(lambda d: "python" in d.get("tags", []))
article = docs.find_one(slug="my-article")

# Update
article['title'] = "Updated Title"
docs.update(article)

# Git integration built-in
docs.commit("Added new article")
docs.push()  # Deploy!

# Rollback
docs.checkout("abc123")  # Git commit hash
```

### Why This Could Be Better Than MongoDB

| Feature | MongoDB | dbbasic-tsv DocumentStore |
|---------|---------|---------------------------|
| Query language | Learn MongoDB query DSL | Just Python |
| Replication | Configure replica sets | `git push` |
| Backup | `mongodump` | `git clone` |
| Version history | Limited/expensive | Full git history |
| View data | Need mongo shell | `cat data.tsv` |
| Diff changes | No | `git diff` shows exactly what changed |
| Rollback | ??? | `git revert` |
| Testing | Separate test DB | `git branch test-env` |
| Ops complexity | High | Zero |
| Cost | $$ (Atlas hosting) | Free |

## When to Use What

### Use dbbasic-tsv + Git when:
- ✅ Content management (blogs, docs)
- ✅ Configuration and settings
- ✅ Product catalogs (descriptions, not inventory)
- ✅ Infrequent writes (one author at a time)
- ✅ Version history is important
- ✅ Human readability matters
- ✅ Zero ops complexity desired
- ✅ Deployment = database update

### Use PostgreSQL/MySQL when:
- ✅ E-commerce transactions (orders, payments)
- ✅ User-generated content (comments, reviews)
- ✅ Real-time inventory
- ✅ High write concurrency
- ✅ ACID guarantees required
- ✅ Complex joins needed
- ✅ Row-level locking required

### Simple Test:
**"Can you safely revert this data with `git revert`?"**
- Yes → Use dbbasic-tsv
- No (would break orders/user data) → Use SQL

## The Deployment Scenarios

### Scenario 1: Static Blog (Perfect)
```
Content: TSV files in git
Deployment: git push → Docker container restart
Database: None needed! Just read from TSV
```

### Scenario 2: Blog with Comments (Hybrid)
```
Content: TSV files in git (posts, pages)
Comments: Small PostgreSQL instance
Deployment: git push for content, PostgreSQL for comments
```

### Scenario 3: E-Commerce (Hybrid)
```
Content: TSV files in git (product descriptions, pages)
Transactions: PostgreSQL (orders, cart, inventory)
Deployment: git push for catalog, PostgreSQL for real-time data
```

### Scenario 4: SaaS App (Wrong Tool)
```
Content: Minimal static content
Transactions: Everything is user-generated
Deployment: PostgreSQL for everything
Note: dbbasic-tsv not appropriate here
```

## The Concurrency Constraint

The fundamental constraint that makes dbbasic-tsv work:

**Single writer, multiple readers** (or very low write concurrency)

This maps perfectly to content publishing:
- One author writes blog post
- Many readers view blog post
- Updates are infrequent
- History matters

This does NOT work for transactions:
- Many customers placing orders simultaneously
- Inventory must update in real-time
- Conflicts are unacceptable
- Current state matters, not history

## Data Storage: TSV as Document Store

Internal representation for document storage:

```
# articles.tsv
id                                  document_json
550e8400-e29b-41d4-a716-446655440000  {"slug":"my-post","title":"Hello",...}
```

Benefits:
- One row per document
- JSON blob stores complex nested data
- Still human-readable (can read JSON)
- Can use any Python data structure
- Easy to query with Python (no special query language)

## Performance Characteristics

### Optimal workloads:
- Read-heavy (90%+ reads)
- Small to medium datasets (<10GB)
- Known access patterns (can index hot fields)
- Append-mostly (inserts > updates)

### Not optimal:
- Write-heavy (high throughput writes)
- Very large datasets (>100GB)
- Unknown query patterns
- Complex multi-table joins

## The Philosophy

Most web applications are:
- 90% content (pages, posts, config)
- 10% transactions (orders, comments, user data)

Yet we build them with:
- 100% PostgreSQL
- Complex ORMs
- Migration management
- Database scaling concerns
- Ops complexity

**Better approach:**
- 90% TSV + Git (zero ops)
- 10% PostgreSQL (only where needed)
- Massive simplicity gain
- Deploy with `git push`

## The Document Database Industry

The document database world spent **billions** building complex systems to solve problems that **Git + TSV + Python** already solved:

- **Replication**: Git has been doing this since 2005
- **Version control**: Git's core feature
- **Conflict resolution**: Git merge tools
- **Distributed collaboration**: Git's strength
- **Human readability**: Text files
- **Diff visualization**: `git diff`
- **Branching/environments**: `git branch`

We just added simple query capabilities on top.

## Summary

dbbasic-tsv + Git is a **document database for content**, not a replacement for transactional databases.

Use it when:
- Your data flows one direction (dev → prod)
- Version history matters
- Simplicity trumps features
- You want to deploy with `git push`

Don't use it when:
- Your data flows both directions
- Transactions are critical
- High write concurrency
- Users generate data in production

The key insight: **Most applications need both**, and mixing them is fine. Use the right tool for each type of data.
