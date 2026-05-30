---
name: ddia-storage-retrieval
description: "Explains and applies storage engine internals from Designing Data-Intensive Applications (Kleppmann, Ch.3) to guide database selection and performance optimization. Use when asked about how databases store or retrieve data, B-Trees vs LSM-Trees, SSTables, WAL, OLTP vs OLAP, column-oriented storage, data warehousing, or index design. Trigger phrases: 'how does a database store data', 'B-Tree vs LSM-Tree', 'which index type should I use', 'optimize read vs write performance', 'explain column store', 'how does OLAP differ from OLTP', 'storage engine internals', 'write-ahead log'. Do NOT use for data model selection (use ddia-foundations), replication strategies (use ddia-replication-partitioning), or serialization formats (use ddia-encoding-evolution)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Storage and Retrieval

Guides analysis and selection of storage engines and index structures based on internals knowledge from Designing Data-Intensive Applications Ch.3. Covers OLTP storage engines (B-Trees, LSM-Trees), OLAP / data warehouse architectures, column-oriented storage, and index design trade-offs.

## Instructions

### Step 1: Classify the Workload

Before recommending any storage approach, classify the workload:

- **OLTP** (Online Transaction Processing): Interactive, user-facing; low-latency reads/writes; small number of records per query; random access patterns.
- **OLAP** (Online Analytical Processing): Analytical; bulk scans of large datasets; aggregate queries over many records; sequential access patterns; batch or periodic.

The storage engine requirements are fundamentally different between these two. Never apply OLTP optimizations to OLAP workloads and vice versa.

### Step 2: Explain or Choose the OLTP Storage Engine

When the context is OLTP, compare the two dominant engine families:

**B-Tree Engines** (PostgreSQL, MySQL InnoDB, LMDB):
- Data organized in fixed-size pages (typically 4 KB) on disk.
- Writes: update in place — overwrite the page containing the record.
- Reads: O(log n) tree traversal.
- Durability: Write-Ahead Log (WAL) — all modifications written to WAL before applied to the tree, enabling crash recovery.
- Strengths: excellent read performance, good for read-heavy workloads, predictable page sizes.
- Weaknesses: write amplification (every write touches a page even for small updates), fragmentation over time.

**LSM-Tree Engines** (LevelDB, RocksDB, Cassandra, HBase, Lucene):
- Write flow: MemTable (in-memory sorted structure) → SSTable files on disk (via compaction).
- Reads: must check MemTable + multiple SSTable levels (use Bloom filters to skip irrelevant SSTables).
- Durability: append-only WAL for MemTable recovery on crash.
- Compaction strategies: Size-Tiered (write-optimized) vs. Leveled (read-optimized, LevelDB default).
- Strengths: sequential disk writes (high write throughput), compression-friendly, no in-place update fragmentation.
- Weaknesses: read amplification (check multiple SSTables), compaction background I/O can interfere with latency, harder to estimate disk usage.

Decision guide:

| Criterion | B-Tree | LSM-Tree |
|---|---|---|
| Write throughput | Lower | Higher |
| Read throughput | Higher (predictable) | Lower (Bloom filters help) |
| Write amplification | High | Lower |
| Space amplification | Low | Higher (until compaction) |
| Latency predictability | High | Variable (compaction spikes) |
| Best for | Read-heavy OLTP | Write-heavy, time-series, logging |

### Step 3: Explain Index Types

Match index type to the access pattern:

- **Primary Index** (clustered): Data rows stored in index order. One per table. B-Trees are default. Enables efficient range scans.
- **Secondary Index**: Additional index on non-primary columns. Can be non-unique. Critical for query optimization.
- **Covering Index**: Stores a copy of additional columns alongside the key so the query can be answered from the index alone (index-only scan), avoiding heap fetch.
- **Multi-column (Composite) Index**: Index on concatenated columns. Efficient for queries filtering on leading prefix columns. Not useful for queries that skip the leading column.
- **Full-text Index**: Inverted index (term → list of document IDs). Used by Lucene/Elasticsearch. Supports fuzzy search, relevance ranking.
- **Fuzzy/Approximate Index**: Levenshtein automata for edit-distance search; useful for spell correction.

Guidance: every index speeds reads but slows writes (must maintain index on every insert/update). Audit index usage regularly.

### Step 4: Explain In-Memory Databases

When latency requirements are extreme:

- **In-memory databases** (Redis, Memcached, VoltDB, MemSQL): Entire dataset in RAM. Durability via periodic snapshots to disk + WAL or async replication.
- Not faster because disk I/O is avoided (OS page cache often means disk data is already in RAM anyway) — but faster because they avoid encoding/decoding overhead of disk format.
- Enable data structures not suited to disk (priority queues, sets) with O(1) operations.
- Anti-cache architectures (NVM, anti-caching): extend RAM to NVM/SSD, evicting least-recently-used data.

### Step 5: Explain OLAP and Data Warehousing

When the workload is analytical:

1. ETL Pipeline: data flows from OLTP systems → Extract → Transform (clean, denormalize) → Load into warehouse.
2. Schema designs:
   - **Star schema**: central fact table (events/transactions) surrounded by dimension tables (who, what, where, when). Simple, good for most analytics.
   - **Snowflake schema**: dimensions further normalized into sub-dimensions. More normalized, harder to query.
3. Recommend column-oriented storage for analytics (see Step 6).

### Step 6: Apply Column-Oriented Storage Principles

Column stores (Redshift, BigQuery, Parquet, Vertica, Dremel) are optimal for OLAP because:

- OLAP queries typically scan a few columns across millions of rows — column layout avoids reading irrelevant data.
- High compression: values in a column have similar domain → dictionary encoding, run-length encoding (RLE), bitpacking.
- Vectorized processing: CPU SIMD instructions operate on compressed column batches efficiently.
- Column sort order: choose sort key by most frequent filter column (e.g., date). Secondary sorts add further compression benefit.
- Replicated copies: store different sort orders on different replicas for different query patterns.
- Materialized views / cubes: precompute common aggregations. Stale on write, but fast on read. Use only when refresh latency is acceptable.

## Examples

### Example 1: Choosing between PostgreSQL and Cassandra

User says: "I'm ingesting 50k IoT sensor readings per second. Should I use PostgreSQL or Cassandra?"

Actions:
1. Classify: write-heavy append workload → LSM-Tree engines preferred.
2. Cassandra uses LSM-Trees → sequential writes, high write throughput.
3. PostgreSQL uses B-Trees → write amplification under heavy load.
4. Ask: what are the read patterns? Time-range queries? Point lookups?
5. Recommend Cassandra for write throughput; note that wide-partition time-series design is critical.

Result: Cassandra with LSM-Tree rationale and time-series schema guidance.

### Example 2: Why are my analytic queries slow on PostgreSQL?

User says: "My SQL queries scanning millions of rows for reports are very slow."

Actions:
1. Identify: analytical scan workload running on OLTP row store.
2. Row stores must read entire rows even when querying 2 out of 50 columns.
3. Options: (a) migrate to columnar store (Redshift, BigQuery, DuckDB); (b) add materialized views for common aggregations; (c) use PostgreSQL with BRIN indexes for sequential-access range scans.
4. Recommend DuckDB for embedded analytics or BigQuery/Redshift for warehouse scale.

Result: Architectural recommendation to separate OLTP and OLAP workloads.

### Example 3: Explain Write-Ahead Log

User says: "How does a database survive a crash without losing data?"

Actions:
1. Explain WAL: every write is first appended sequentially to the WAL (durable on disk).
2. On crash: WAL is replayed to reconstruct in-memory state or complete partial page writes.
3. This makes B-Tree writes crash-safe despite in-place page updates.
4. LSM-Trees also use WAL to recover the in-memory MemTable.

Result: Clear WAL explanation with role in both B-Tree and LSM-Tree engines.

## Troubleshooting

### LSM-Tree compaction causing latency spikes
Cause: Background compaction consumes I/O bandwidth, competing with foreground reads.
Solution: Use leveled compaction (more predictable I/O); tune compaction thread priority; use SSDs to reduce I/O contention; monitor compaction lag metrics.

### Index not being used by query planner
Cause: Query pattern does not match index leading column; low cardinality columns; planner estimates full scan is cheaper.
Solution: Run EXPLAIN ANALYZE; check leading column coverage; consider composite index with correct column order; analyze table statistics freshness.

### Column store performs worse than expected for small queries
Cause: Column stores shine on full-column scans; for point lookups (single row by PK), row stores are faster.
Solution: Maintain a separate OLTP row store for point-lookup access patterns; route analytical scans to the column store.
