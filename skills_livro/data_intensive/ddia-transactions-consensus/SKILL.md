---
name: ddia-transactions-consensus
description: "Applies transactions, distributed faults, and consistency principles from Designing Data-Intensive Applications (Kleppmann, Ch.7-8-9) to reason about correctness in distributed systems. Use when asked about ACID, isolation levels, race conditions, distributed transactions, 2PC, consensus algorithms, linearizability, CAP theorem, eventual consistency, or how distributed systems fail. Trigger phrases: 'explain ACID', 'what isolation level should I use', 'how to avoid dirty reads', 'phantom reads', 'serializable isolation', 'distributed transaction', 'two-phase commit', 'what is linearizability', 'CAP theorem explained', 'how does Raft work', 'how does ZooKeeper work', 'split-brain problem', 'why clocks are unreliable in distributed systems'. Do NOT use for replication topology selection (use ddia-replication-partitioning), storage engine choice (use ddia-storage-retrieval), or stream/batch processing design (use ddia-batch-stream-processing)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Transactions and Distributed Consensus

Guides reasoning about correctness in distributed systems — transactions, isolation levels, the fundamental difficulties of distributed computing, and consensus algorithms — based on Designing Data-Intensive Applications Ch.7-8-9.

## Instructions

### Step 1: Clarify the Correctness Concern

Identify the category of problem:

- **Transaction / concurrency bug**: dirty read, non-repeatable read, phantom read, write skew, lost update → address with isolation levels (Step 2).
- **Distributed systems failure**: network partition, clock skew, process pause → address with fault model (Step 3).
- **Consistency guarantee**: linearizability, causal consistency, eventual consistency → address with consistency model (Step 4).
- **Distributed coordination**: leader election, locks, atomic commit → address with consensus (Step 5).

### Step 2: Apply Transaction Isolation Levels

Transactions provide ACID guarantees. Focus on **Isolation** — the I in ACID — which protects against concurrency anomalies.

**Anomaly catalog** (from weakest to strongest protection needed):

| Anomaly | Description | Example |
|---|---|---|
| Dirty Read | Read uncommitted data from a concurrent transaction | Account balance reads include a transfer not yet committed |
| Dirty Write | Overwrite uncommitted write from another transaction | Two buyers overwrite each other's reservation |
| Read Skew (Non-repeatable Read) | Same query returns different results within one transaction | Balance reads inconsistently during a transfer |
| Lost Update | Concurrent read-modify-write cycles overwrite each other | Two users increment a counter simultaneously |
| Write Skew | Transaction reads something, makes a decision based on it, writes; but by commit time the premise is false | Two doctors simultaneously un-on-call assuming the other is on call |
| Phantom Read | A write in another transaction affects results of a search query in current transaction | Count of active records changes mid-transaction |

**Isolation levels** (weakest to strongest):

| Level | Prevents | Implementation |
|---|---|---|
| Read Uncommitted | (nothing) | No locks on reads |
| Read Committed | Dirty Reads, Dirty Writes | Row-level locks on writes; snapshot on reads |
| Repeatable Read | + Read Skew, Lost Updates | Snapshot isolation (MVCC) |
| Serializable | ALL anomalies including Write Skew, Phantoms | SSI, 2PL, or serializable execution |

**Implementations of Serializable Isolation**:
1. **Actual Serial Execution** (VoltDB, Redis, H-Store): single-threaded, in-memory, stored procedures for batches. Works when dataset fits in RAM and transactions are short.
2. **Two-Phase Locking (2PL)**: readers block writers, writers block readers (unlike MVCC). Growing phase acquires locks; shrinking phase releases. Risk: deadlocks (detect via cycle detection in wait-for graph; resolve by aborting one transaction).
3. **Serializable Snapshot Isolation (SSI)** (PostgreSQL default since v9.1, FoundationDB): optimistic — reads proceed without blocking; on commit, detect if any reads observed stale data and abort if so. Better throughput than 2PL under low contention.

**Recommendation**: default to Read Committed (most databases' default). Upgrade to Repeatable Read / SSI when you detect write skew or phantom read bugs. Avoid Read Uncommitted entirely.

**Lost update prevention techniques** (even without full serializability):
- Atomic operations: `UPDATE counter SET value = value + 1 WHERE id = X` (atomic in most databases).
- Explicit locking: `SELECT ... FOR UPDATE` acquires a row lock.
- Compare-and-set: `UPDATE WHERE value = $expected_value` — retries if changed.

### Step 3: Apply the Distributed Faults Model

Distributed systems are not just networked computers — they are fundamentally different from single-node systems due to partial failures.

**Unreliable networks**:
- A request may be lost, the remote node may be slow/dead, or the response may be lost.
- You cannot distinguish between "node is dead" and "network is slow" from the outside.
- Timeout is the only mechanism to detect node failure — but timeout duration is a trade-off (too short = false positives; too long = slow failure detection).
- Design for: idempotent requests (safe to retry), explicit acknowledgment, timeouts with retry + backoff + jitter.

**Unreliable clocks**:
- Wall clocks (time-of-day): subject to NTP sync, can jump forward or backward. Do NOT use for event ordering.
- Monotonic clocks: measure elapsed time; safe for timeouts and intervals. NOT comparable across nodes.
- Google TrueTime (Spanner): hardware atomic clocks + GPS → bounded uncertainty window [earliest, latest]. Spanner waits out the uncertainty before committing → linearizable commits with global time.
- Practical rule: do not rely on clocks for ordering events across distributed nodes. Use logical clocks (Lamport timestamps, version vectors) instead.

**Process pauses**:
- A process can pause for arbitrarily long (GC stop-the-world, OS scheduling, VM migration, swap).
- A node cannot know if it was paused — it wakes up and assumes it's still the leader.
- Fencing tokens: monotonically increasing token issued with each lease; storage server rejects writes with old tokens. Prevents stale leaders from causing split-brain corruption.

**Byzantine faults**: nodes that send malicious or incorrect messages (not just crash). Byzantine fault tolerance (BFT) requires 3f+1 nodes to tolerate f byzantine nodes. Only necessary in adversarial environments (blockchain). Most data systems assume non-Byzantine (crash-fault) models.

### Step 4: Apply Consistency Models

**Linearizability** (strongest): behaves as if there is only one copy of the data; all operations appear instantaneous and in a globally consistent order. Every read returns the most recent write.
- Requires: leader-based single copy or consensus protocol.
- Comes at a cost: higher latency (must coordinate with majority), unavailable during network partition (CAP theorem).
- Use when: financial transactions, leader election, uniqueness constraints, coordination.

**Causal Consistency**: operations that are causally related appear in the correct order to all nodes; concurrent operations may be seen in different orders. Weaker than linearizability but avoids coordination overhead.
- Implementation: version vectors (track per-node sequence numbers); each node attaches its version vector to messages.

**Eventual Consistency**: given no new writes, all replicas will eventually converge. Says nothing about when or ordering.
- Strong Eventual Consistency (SEC) + CRDTs: convergence is guaranteed to produce the same result (not just eventual convergence, but convergent to a specific correct value).

**CAP Theorem** (Brewer): a distributed system under a network partition can be either Consistent (linearizable) or Available, but not both. Modern framing: every distributed system must handle network partitions → choice is between linearizability and availability during a partition.

**PACELC** (more nuanced): Even without partition (normal operation): trade-off between Latency and Consistency. Riak, Cassandra: PA/EL (high availability, low latency, eventual consistency). Zookeeper, HBase: PC/EC (linearizable, higher latency).

### Step 5: Apply Consensus Algorithms

Consensus = getting multiple nodes to agree on a value despite failures.

**Two-Phase Commit (2PC)**:
- Phase 1 (Prepare): coordinator sends PREPARE to all participants; each votes yes/no.
- Phase 2 (Commit/Abort): if all voted yes → coordinator sends COMMIT; otherwise ABORT.
- Problem: coordinator single point of failure — if coordinator crashes after Phase 1, participants are stuck in uncertain state (cannot commit or abort without coordinator). Blocking protocol.
- Use 2PC only for multi-database transactions where performance is secondary to atomicity. Use XA transactions for heterogeneous systems.

**Raft / Paxos (Fault-tolerant Consensus)**:
- Raft: leader-based; clients send writes to the leader; leader replicates to followers; committed when majority acknowledges.
- Leader election: node with the most up-to-date log wins election (Raft term/vote mechanism).
- Guarantees: linearizable reads from the leader; tolerates minority node failures (f failures in 2f+1 cluster).
- Implementations: etcd, Consul, ZooKeeper (ZAB protocol, similar to Paxos).

**ZooKeeper** (coordination service built on ZAB consensus):
- Use cases: leader election, distributed locks, service discovery, configuration management.
- Locks via ephemeral nodes: node creates an ephemeral znode; znode disappears if the client dies → automatic lock release.
- Fencing tokens: monotonically increasing transaction IDs (zxid) → safe as fencing tokens for preventing stale leaders.

**Epoch numbers / generation numbers**: increment on every leader election. Include in all writes; storage/consumers reject writes from old leaders.

## Examples

### Example 1: Diagnosing a write skew bug

User says: "Two doctors can both take themselves off the on-call list simultaneously, leaving nobody on call."

Actions:
1. Identify: Write Skew — each reads "is someone else on call?" (yes), then writes "I'm going off call" — both pass the check, both write.
2. Repeatable Read / MVCC does NOT prevent write skew (reads snapshot, does not lock).
3. Fix options: (a) Serializable isolation (SSI in PostgreSQL); (b) explicit `SELECT COUNT(*) FOR UPDATE` on the on-call list to lock the premise rows; (c) redesign: maintain an atomic `on_call_count` counter and use `CHECK CONSTRAINT >= 1`.

Result: Serializable isolation or materializing the conflict via a counter.

### Example 2: Choosing between linearizability and eventual consistency for a health alert system

User says: "Our dengue alert system sends notifications when case counts exceed a threshold. Does it need linearizability?"

Actions:
1. Classify: threshold detection requires that all nodes agree on whether the threshold was crossed.
2. Eventual consistency: two nodes may disagree → duplicate or missed alerts.
3. Causal consistency: sufficient if alert is based on a single counter (not cross-entity comparison).
4. Recommend: use a linearizable counter (Redis INCR on a single shard, or an atomic counter via ZooKeeper) for the threshold check; downstream alert fan-out can be eventually consistent.

Result: Linearizable counter for threshold; eventual consistency for notification fan-out.

### Example 3: Distributed lock for preventing duplicate batch jobs

User says: "We have 3 worker nodes. Only one should run the weekly aggregation job. How do we ensure this?"

Actions:
1. Leader election via ZooKeeper or etcd: workers compete for an ephemeral lock.
2. Winner runs the job; if it dies, the ephemeral node disappears → another worker takes over.
3. Add fencing token: job runner attaches epoch number to all database writes; storage layer rejects writes from old epoch if a new leader was elected mid-job.

Result: ZooKeeper leader election + fencing token pattern.

## Troubleshooting

### 2PC coordinator crashed — participants stuck in doubt
Cause: Coordinator failed after sending PREPARE but before sending COMMIT/ABORT. Participants hold locks and cannot proceed.
Solution: Recover coordinator from durable log; if unavailable, manually resolve by querying participants' in-doubt transaction lists and deciding externally. Long-term: replace 2PC with a consensus protocol (Raft-based distributed transaction manager).

### Repeated leader elections (split-brain oscillation)
Cause: Network partition causes followers to think leader is dead and start new elections; leader recovers and conflicts.
Solution: Ensure only one leader can hold a fencing token at a time. Use ZooKeeper's ephemeral nodes. Tune election timeout to be significantly longer than expected network recovery time.

### Serializable isolation degrading write performance
Cause: SSI aborts too many transactions under high contention; 2PL causes deadlocks under high write concurrency.
Solution: Reduce transaction scope (shorter transactions = fewer conflicts). Use atomic operations instead of read-modify-write loops. Consider actual serial execution (VoltDB) if dataset fits in RAM and transactions are simple.
