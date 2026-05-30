---
name: ddia-replication-partitioning
description: "Applies replication and partitioning principles from Designing Data-Intensive Applications (Kleppmann, Ch.5-6) to design distributed data systems. Use when asked about database replication, leader-follower setup, multi-leader replication, leaderless databases, replication lag, conflict resolution, sharding, partitioning strategies, hot spots, or secondary indexes in distributed systems. Trigger phrases: 'how to replicate data across nodes', 'leader vs leaderless replication', 'how to shard a database', 'partitioning by key range vs hash', 'handle write conflicts in distributed DB', 'replication lag problems', 'how Cassandra handles writes', 'consistent hashing', 'secondary index in sharded DB'. Do NOT use for consistency and consensus theory (use ddia-transactions-consensus), storage engine internals (use ddia-storage-retrieval), or batch/stream pipeline design (use ddia-batch-stream-processing)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Replication and Partitioning

Guides design and troubleshooting of distributed data systems with replication and partitioning, based on Designing Data-Intensive Applications Ch.5-6. Covers all major replication topologies, conflict resolution strategies, partitioning schemes, and distributed secondary index patterns.

## Instructions

### Step 1: Identify the Distribution Goal

Before recommending a replication or partitioning strategy, clarify the driving requirement:

- **High Availability**: survive node failures without downtime → replication.
- **Read Scalability**: serve more reads → read replicas (replication).
- **Write Scalability / Large Datasets**: data too large for one node → partitioning.
- **Geographic Distribution**: low latency for users in multiple regions → multi-leader or leaderless replication.

### Step 2: Apply Replication Topology

**Single-Leader (Leader-Follower) Replication** (PostgreSQL streaming replication, MySQL binlog, MongoDB):
- All writes go to the leader; leader writes to a replication log.
- Followers apply the log → eventually have the same data.
- Reads can be served from followers (read scaling), but may be stale.
- Follower failure: catch up from replication log.
- Leader failure: failover — promote a follower; risk of split-brain if not managed carefully.
- Replication log types: statement-based (fragile — NOW(), random functions), WAL shipping (storage-engine coupled), row-based / logical (recommended — format-independent, most databases default).

Replication lag problems and mitigations:
- **Read-your-own-writes**: after a user writes, reads may hit a stale replica. Fix: route that user's reads to leader for 1 minute after write, or use monotonic read guarantees.
- **Monotonic reads**: different replicas may show different points in time. Fix: hash user ID to always read from the same replica.
- **Consistent prefix reads**: related records may appear out of order. Fix: write causally related records to the same partition.

**Multi-Leader Replication** (Tungsten Replicator, BDR, CockroachDB, Google Docs):
- Multiple leaders accept writes; leaders replicate to each other.
- Use cases: multiple data centers (one leader per DC), offline clients, collaborative editing.
- Key challenge: write conflicts when the same record is modified concurrently on two leaders.
- Conflict resolution strategies:
  1. Last Write Wins (LWW): attach timestamp; last timestamp wins. Simple but loses data.
  2. Merge: concatenate conflicting values (e.g., version vectors).
  3. Record conflict: expose conflict to application, let user resolve (CouchDB model).
  4. CRDT (Conflict-free Replicated Data Types): data structures that merge deterministically (counters, sets, sequences).
- Replication topologies: circular, star, all-to-all. All-to-all is most robust (no single point of failure in the replication path) but risks causal ordering violations — use version vectors to detect.

**Leaderless Replication** (Dynamo-style: Amazon DynamoDB, Cassandra, Riak, Voldemort):
- No designated leader; clients write to multiple replicas directly (or via a coordinator).
- **Quorum reads/writes**: W + R > N guarantees at least one node returned is up-to-date.
  - N = replication factor, W = write quorum, R = read quorum.
  - Common: N=3, W=2, R=2 (tolerates 1 node failure).
- **Read repair**: on a read, if responses differ, the stale replica is updated immediately.
- **Anti-entropy**: background process compares replicas and syncs divergences (no ordering guarantee).
- Sloppy quorum: during network partition, writes go to reachable nodes outside the home set (hinted handoff). Increases availability, relaxes consistency.

### Step 3: Apply Partitioning Strategy

Partitioning (sharding) splits large datasets across multiple nodes.

**Key Range Partitioning** (HBase, Bigtable, MongoDB):
- Assign a contiguous range of keys to each partition.
- Pros: efficient range scans (e.g., date range queries).
- Cons: hot spots if writes are skewed to a key range (e.g., all writes go to "today's" partition).
- Mitigation: add random prefix to hot keys (splits writes across partitions at the cost of scatter-gather reads).

**Hash Partitioning** (Consistent Hashing — Cassandra, Voldemort):
- Hash the key → distribute uniformly across partitions.
- Pros: eliminates hot spots for random writes.
- Cons: destroys key ordering — range queries require full scatter-gather.
- Consistent hashing: each node covers a range of the hash ring; adding/removing a node moves only K/N keys (K=total keys, N=nodes). Cassandra uses virtual nodes (vnodes) for more uniform distribution.

**Hybrid**: Cassandra compound primary key: first part → hash partition (partition key), second part → sort within partition (clustering key). Enables partitioned range scans.

**Skewed workloads and hot spots**: even hash partitioning can't eliminate hot spots if a single key is extremely popular (e.g., a celebrity user). Application-level mitigation: append random suffix to hot key → write to N sub-keys → reads must merge N sub-keys.

### Step 4: Handle Secondary Indexes with Partitioning

Secondary indexes in partitioned databases require special design:

**Local Secondary Index (Document-partitioned)**:
- Each partition maintains its own secondary index covering only its local data.
- Write: update local index only (simple).
- Read on secondary key: must query ALL partitions and merge (scatter-gather). Can be slow if many partitions.
- Used by: MongoDB, Riak, Cassandra (materialized views), Elasticsearch.

**Global Secondary Index (Term-partitioned)**:
- Index itself is partitioned by the indexed term (not by the primary key).
- Read: query specific partition(s) that own the index range → fast reads.
- Write: a single write may update multiple index partitions (secondary index is updated asynchronously in most implementations).
- Used by: DynamoDB GSI, Riak's search.
- Caution: asynchronous GSI updates mean reads on the GSI may be stale.

### Step 5: Explain Rebalancing Strategies

When nodes are added/removed, data must be redistributed:

- **Fixed number of partitions**: create many more partitions than nodes (e.g., 1000 partitions for 10 nodes). When a node is added, steal partitions from other nodes. Used by: Elasticsearch, Riak, Voldemort.
- **Dynamic partitioning**: partitions split when they exceed a size threshold; merge when below. Adapts to data size automatically. Used by: HBase, MongoDB.
- **Proportional to nodes**: fixed number of partitions per node. When a node is added, it creates partitions and steals from existing nodes. Used by: Cassandra.
- Avoid automatic rebalancing in production systems without operator approval — a failing node + automatic rebalancing can overload the rest of the cluster.

## Examples

### Example 1: Multi-datacenter replication for an epidemiological surveillance system

User says: "We need our dengue case database to be available in 3 cities simultaneously. How do we replicate?"

Actions:
1. Classify: geographic distribution + high availability → multi-leader (one leader per city).
2. Writes happen locally (low latency for field workers).
3. Conflict resolution: LWW may lose concurrent updates to the same case record → recommend CRDT counters for aggregate counts; merge-based resolution for case detail updates.
4. Network partition between cities: each city remains operational (local leader); reconcile on reconnect.

Result: Multi-leader architecture with city-level leaders and CRDT-based conflict resolution for count aggregations.

### Example 2: Hot spot on date-partitioned time-series data

User says: "Our Cassandra cluster is heavily loaded on the most recent partition while old ones are idle."

Actions:
1. Identify: key range partitioning on date → all writes go to "today" partition (hot spot).
2. Fix: use a compound partition key: (date, bucket) where bucket = hash(some_field) % N → distribute writes for the same date across N partitions.
3. Reads: query all N buckets for a given date → aggregate in application.

Result: Salted compound partition key to distribute hot spot writes.

### Example 3: Quorum reads/writes for availability vs. consistency

User says: "How do I configure Cassandra to be strongly consistent vs. eventually consistent?"

Actions:
1. N=3 (replication factor).
2. Strong consistency: W=2, R=2 (W+R > N). Every read sees every committed write.
3. High availability, eventual consistency: W=1, R=1. Fastest, but may return stale data.
4. Recommended default: W=QUORUM, R=QUORUM (2 each for N=3). Good balance.
5. Note: quorum does not guarantee linearizability — concurrent writes can still create anomalies (need additional consensus for linearizable operations).

Result: Quorum configuration guide with trade-off explanation.

## Troubleshooting

### Read-your-own-writes violation after a write
Cause: Write went to leader; subsequent read went to stale follower before replication lag was resolved.
Solution: For 1 minute after any write by a user, route that user's reads to the leader. Or use synchronous replication for critical paths (with availability trade-off).

### Rebalancing overloading cluster
Cause: Automatic rebalancing triggered during a node failure, moving data while cluster is already degraded.
Solution: Disable automatic rebalancing; require operator approval for rebalancing events. Add capacity gradually.

### Secondary index scatter-gather is too slow
Cause: Local (document-partitioned) secondary index requires querying all N partitions.
Solution: Migrate to a global (term-partitioned) secondary index, or use a dedicated search index (Elasticsearch) with async sync from primary store.
