---
name: ddia-batch-stream-processing
description: "Applies batch processing, stream processing, and future data system architecture principles from Designing Data-Intensive Applications (Kleppmann, Ch.10-11-12) to design data pipelines. Use when asked about MapReduce, dataflow engines, Apache Spark, Flink, Kafka Streams, event sourcing, CQRS, change data capture, Lambda architecture, Kappa architecture, stream-table duality, CEP, or how to build reliable data pipelines. Trigger phrases: 'how does MapReduce work', 'design a data pipeline', 'event sourcing vs CRUD', 'change data capture CDC', 'Lambda vs Kappa architecture', 'stream processing vs batch processing', 'how Kafka Streams works', 'exactly-once semantics in streams', 'CEP complex event processing', 'how to build a data lake'. Do NOT use for replication or partitioning of raw storage (use ddia-replication-partitioning), transaction isolation (use ddia-transactions-consensus), or storage engine internals (use ddia-storage-retrieval)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Batch and Stream Processing

Guides design of data pipelines — batch processing (MapReduce and modern dataflow), stream processing (Kafka, Flink, Kafka Streams), and future-facing architectures (Lambda, Kappa, event sourcing, CQRS) — based on Designing Data-Intensive Applications Ch.10-11-12.

## Instructions

### Step 1: Classify the Processing Pattern

Choose the processing model based on data freshness and volume requirements:

- **Batch Processing**: processes a bounded, finite dataset at rest (daily/hourly jobs). High throughput, high latency (minutes to hours). Examples: ETL jobs, monthly reports, ML model training.
- **Stream Processing**: processes an unbounded, continuous stream of events in near-real-time. Low latency (milliseconds to seconds). Examples: fraud detection, dashboards, alerting.
- **Micro-batch**: artificial boundaries imposed on streams (Spark Streaming). Simulates streaming via small batch intervals. Compromise between the two.
- **Lambda Architecture**: runs batch and stream in parallel; batch is the source of truth; stream is the approximation layer; results are merged. Complex to maintain two codebases.
- **Kappa Architecture**: stream-only; use a replayable log (Kafka with long retention) as the source of truth; re-process by replaying the log. Simpler than Lambda; preferred when stream processing engine is mature enough.

### Step 2: Apply Batch Processing Principles (MapReduce / Dataflow)

**MapReduce** (Hadoop):
- Map phase: user-defined function applied to each record → emits (key, value) pairs.
- Shuffle/Sort: framework groups all values by key across all mappers.
- Reduce phase: user-defined function aggregates values per key.
- Key property: **fault tolerance via materialization** — every map output is written to disk before reduce starts. Allows any task to be retried on any node.
- Limitations: many jobs require chaining (output of job 1 → input of job 2), causing excessive intermediate disk I/O.

**Modern Dataflow Engines** (Spark, Flink, Tez, Beam):
- Replace MapReduce's excessive materialization with **pipelined execution** — operators stream data between stages in memory.
- Spark: RDD/DataFrame API; lazy evaluation; fault tolerance via lineage (re-compute lost partitions from RDDs). Better for batch analytics.
- Flink: streaming-first engine; also supports batch as a special case of streaming. True low-latency streaming with sophisticated state management.
- Apache Beam: unified API that runs on Spark, Flink, or Dataflow runners. Write once, run on multiple backends.

**Join types in batch** (mirroring SQL joins):
- Sort-merge join: sort both datasets by join key; merge-join. Standard MapReduce join.
- Broadcast hash join: if one dataset fits in memory, broadcast it to all mappers; lookup in-memory hash map. Very fast.
- Partitioned hash join (bucketed join): both datasets co-partitioned by the same key; join locally on each partition.

**Output modes**:
- Build search indexes (Lucene): write index files to HDFS/S3; swap into production atomically.
- Build key-value stores (Voldemort): produce database files from batch; bulk-load into production database.
- Push to OLAP store (Redshift/BigQuery).

### Step 3: Apply Stream Processing Principles

**Message brokers vs. event logs**:

| Property | Traditional MQ (RabbitMQ, ActiveMQ) | Log-based broker (Kafka, Kinesis) |
|---|---|---|
| Delivery | Delete on ACK | Retain log; consumers track offset |
| Replay | No | Yes (rewind offset) |
| Fan-out | Via subscriptions | Multiple consumer groups independently |
| Order | Per-queue | Per-partition |
| Scale | Limited | Partitioned → horizontal scale |

Recommend **Kafka (log-based)** for event-driven data pipelines. Recommend **RabbitMQ** only for simple task queues needing work distribution to heterogeneous workers.

**Kafka fundamentals**:
- Topics are divided into **partitions** (the unit of parallelism and ordering).
- Within a partition, messages are strictly ordered; across partitions, no global order.
- Consumer group: one consumer per partition; scaling requires re-partitioning.
- Offset: consumer's read position. Stored in Kafka itself or externally.
- Compacted topics: Kafka retains only the latest value per key → enables indefinite state reconstruction (like a database changelog).

**Stream processing patterns**:

1. **Stateless transformations**: filter, map, project — no state needed; fully parallelizable.
2. **Stateful aggregations**: count, sum, average over a window — requires state per key.
3. **Windowing**:
   - Tumbling window: fixed non-overlapping intervals (e.g., 1-hour buckets).
   - Hopping window: fixed intervals with overlap (e.g., 1-hour window sliding every 5 minutes).
   - Sliding window: window defined by event proximity (events within 5 minutes of each other).
   - Session window: groups events by inactivity gap (e.g., user session ends after 30 minutes idle).
4. **Stream-table join**: stream of events joined with a current state table (e.g., enrich each event with user profile). The table is a materialized view of a changelog.
5. **Stream-stream join**: join two event streams within a time window (both sides buffered in state).
6. **Table-table join**: materialized view of both tables; update output whenever either input changes.

**Late data and watermarks**:
- Events arrive out-of-order due to network delays (especially IoT sensors).
- **Watermark**: the system's assertion that all events up to timestamp T have arrived. Events after the watermark is passed are treated as late.
- Policy for late events: (a) ignore; (b) update the affected window and retransmit the corrected result; (c) use a side output for late events.

**Exactly-once semantics**:
- At-most-once: fire and forget. May lose events.
- At-least-once: retry on failure. May duplicate events. Require idempotent consumers.
- Exactly-once: Kafka Transactions + idempotent producers + transactional consumers. The most expensive but correct.
- Effectively-once: idempotent consumers + at-least-once delivery (common practical approach).

### Step 4: Apply Event Sourcing, CDC, and CQRS

**Change Data Capture (CDC)**:
- Capture every write to a database as a stream of change events.
- Sources: Debezium (MySQL/PostgreSQL binlog → Kafka), AWS DMS, Maxwell.
- Use: synchronize primary DB with derived data stores (search index, cache, data warehouse) without dual-write bugs.
- Log compaction: replay full history → rebuild derived stores from scratch.

**Event Sourcing**:
- Instead of storing current state, store a log of immutable events (the facts of what happened).
- Current state = fold/reduce over the event log.
- Advantages: complete audit trail; ability to replay history; derive multiple views from same event log; temporal queries ("what was the state on date X?").
- Contrast with CDC: CDC captures low-level DB mutations; event sourcing stores high-level domain events.

**CQRS (Command Query Responsibility Segregation)**:
- Separate the write model (commands) from the read model (queries).
- Write model: validate command, append event to log.
- Read model: one or more materialized projections optimized for specific query patterns, built from the event log.
- Enables: independent scaling of read and write paths; multiple specialized read models from the same event source.

### Step 5: Apply Future Architecture Patterns

**Unbundling the database** (DDIA Ch.12 thesis):
- Modern data architectures separate the concerns of a monolithic database: durable storage (S3/GCS), indexing (Elasticsearch), query engine (Spark/Flink), transactions (Kafka Transactions, DynamoDB), derived views (materialized views via stream processing).
- Use a **log as the integration backbone**: all state changes are events in a log; consumers derive their own read-optimized stores.

**Derived data and correctness**:
- Write to one authoritative source (the log); all other stores are derived (eventually consistent copies).
- If a derived store becomes corrupted, rebuild by replaying the log. Makes the system self-healing.
- Dataflow integrity: end-to-end correctness requires exactly-once or idempotent processing throughout the pipeline.

**Ethics and data**:
- Predictive systems can create feedback loops (e.g., predictive policing amplifies historical bias).
- Right to explanation: users affected by automated decisions deserve to understand the basis.
- Data minimization: collect only what is needed; delete when no longer necessary.
- Apply these principles when designing data pipelines that affect humans.

## Examples

### Example 1: Dengue surveillance data pipeline design

User says: "We need to aggregate weekly dengue case reports from 300 municipalities in near-real-time and update a dashboard."

Actions:
1. Classify: stream processing (near-real-time dashboard updates).
2. Ingest: municipalities push case events to Kafka (topic: `dengue-cases`, partitioned by municipality ID).
3. Stream processor (Flink or Kafka Streams): tumbling 7-day windows, aggregate case counts per municipality per week.
4. Output: write aggregated results to a read-optimized store (PostgreSQL or Elasticsearch) for dashboard queries.
5. Late data: municipalities may report with delay → use a 24-hour watermark; retransmit corrected weekly totals when late events arrive.

Result: Kafka → Flink windowed aggregation → Elasticsearch dashboard pipeline.

### Example 2: Migrating from dual-write to CDC

User says: "We write to our main database and then try to update Elasticsearch manually. It gets out of sync constantly."

Actions:
1. Identify: dual-write anti-pattern — two writes are not atomic; one can fail while the other succeeds.
2. Replace with CDC: Debezium captures PostgreSQL WAL changes → publishes to Kafka → Elasticsearch sink connector consumes and indexes.
3. Single writer (the DB); Elasticsearch is a derived store.
4. On Elasticsearch corruption: replay Debezium topic from offset 0 → rebuild index.

Result: CDC pipeline eliminating dual-write inconsistency.

### Example 3: Lambda vs. Kappa for a historical + real-time analytics system

User says: "We need real-time alerting on dengue cases AND monthly historical trend reports. Should we use Lambda or Kappa?"

Actions:
1. Lambda: batch layer (Spark on S3) for monthly reports; speed layer (Kafka Streams) for real-time alerts. Two codebases to maintain; eventual consistency between layers.
2. Kappa: Kafka with long retention (90 days) as the source of truth. Kafka Streams for real-time alerts. For monthly reports, a separate Flink job replays the last 30 days.
3. Recommend Kappa: simpler, single codebase. Flink can handle both real-time and batch-like replays from the same Kafka topic. Avoid Lambda unless the batch processing requirements are too complex for stream reprocessing.

Result: Kappa architecture with Flink as the unified processing engine.

## Troubleshooting

### Stream processing lagging behind real-time
Cause: Consumer is slower than producer; partition backlog is growing.
Solution: Scale up consumers (add more instances, each taking one partition); optimize per-event processing time; increase partition count (requires redistributing existing offsets carefully).

### Late events causing incorrect window results
Cause: Watermark is too aggressive (set too early); events from slow sources arrive after the window closed.
Solution: Increase watermark lag; implement allowed lateness with window recomputation; route very late events to a side output for manual reconciliation.

### Event sourcing event log growing unboundedly
Cause: Every event is retained; log volume grows proportionally to all historical writes.
Solution: Implement snapshotting — periodically persist a full state snapshot; only replay events after the snapshot timestamp. Compacted Kafka topics retain only the latest value per key for key-value state.

### Exactly-once processing too slow
Cause: Kafka transactions add latency (transaction coordinator round-trips); all-or-nothing commit overhead.
Solution: Evaluate if exactly-once is truly required or if idempotent consumers + at-least-once is sufficient. Use producer batching + larger transaction intervals to amortize overhead. Consider Flink's checkpoint-based exactly-once (lower overhead than Kafka Transactions for stateful processing).
