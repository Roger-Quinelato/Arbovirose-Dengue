---
name: ddia-foundations
description: "Applies core principles from Designing Data-Intensive Applications (Kleppmann, Ch.1-2) to evaluate and design data systems. Use when asked about reliability, scalability, maintainability, fault tolerance, data models (relational, document, graph), query languages (SQL, MapReduce, Cypher, SPARQL), or trade-offs between data representations. Trigger phrases: 'design a reliable system', 'choose a data model', 'relational vs document database', 'how to scale this', 'explain CAP', 'graph database vs relational', 'what data model fits my use case'. Do NOT use for storage engine internals (use ddia-storage-retrieval), distributed replication (use ddia-replication-partitioning), or transactions (use ddia-transactions-consensus)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Foundations

Guides the design and evaluation of data-intensive systems based on the three pillars of the Designing Data-Intensive Applications framework: **Reliability**, **Scalability**, and **Maintainability**, plus selection of the right **Data Model** for the problem at hand.

## Instructions

### Step 1: Identify the Design Goal

Determine which pillar the user's question primarily addresses:

- **Reliability**: System must work correctly despite hardware faults, software bugs, or human errors.
- **Scalability**: System must handle growth in data volume, traffic volume, or complexity.
- **Maintainability**: System must be operable, simple to reason about, and evolvable over time.

Apply these definitions operationally, not just conceptually. Ask: *What exactly is the failure mode or growth concern?*

### Step 2: Apply Reliability Reasoning

When the concern is fault tolerance:

1. Distinguish **fault** (component deviation) from **failure** (system stops serving users).
2. Enumerate fault categories: hardware faults (independent, MTTF-based), software faults (systematic, correlated), human errors (leading cause of outages).
3. Recommend mitigations per category:
   - Hardware: RAID, redundant power, multi-machine redundancy, rolling upgrades.
   - Software: process isolation, crash-and-restart, self-checking invariants (e.g., message queue in = out), chaos engineering (Netflix Chaos Monkey pattern).
   - Human: well-designed abstractions/APIs, sandbox environments, gradual rollouts, observability (metrics, alerts, telemetry).

### Step 3: Apply Scalability Reasoning

When the concern is handling load growth:

1. Define **load parameters** precisely for the system (requests/sec, read/write ratio, active users, fan-out factor, cache hit rate).
2. Analyze two dimensions:
   - Performance under fixed resources as load increases (throughput degradation, response time percentiles — use p50, p95, p99, p999, NOT averages alone).
   - Resources required to maintain constant performance as load scales.
3. Choose scaling approach:
   - **Vertical scaling** (scale-up): simpler, limited ceiling.
   - **Horizontal scaling** (scale-out, shared-nothing): complex but unbounded; stateless services scale easily, stateful systems require careful partitioning.
   - **Elastic scaling**: auto-provision based on load; preferred when load is unpredictable.
4. Warn: there is no single scalable architecture — it is always specific to the application's read/write patterns and access patterns.

### Step 4: Apply Maintainability Reasoning

When the concern is long-term operability:

1. **Operability**: Make routine tasks easy — monitoring, capacity planning, deployment, dependency updates, graceful degradation, good default behavior.
2. **Simplicity**: Remove accidental complexity. Use abstractions that hide implementation details. Flag state explosion, tight coupling, special-casing.
3. **Evolvability** (extensibility/plasticity): Anticipate changing requirements. Prefer systems that allow incremental changes, backward-compatible schemas, and incremental rollouts.

### Step 5: Select the Right Data Model

When the question is about data representation or database type:

1. **Relational Model** (SQL): Best for structured data with many-to-many relationships, complex joins, strong consistency guarantees. Data normalization reduces redundancy. Use when relationships are the primary concern.
2. **Document Model** (MongoDB, CouchDB, RethinkDB): Best for self-contained documents with one-to-many relationships, locality of access, schema flexibility. Avoid when you need joins across document types or many-to-many relations — these degrade into application-side join hell.
3. **Graph Model** (Neo4j, Titan, Datomic): Best when anything can be related to anything — social networks, fraud detection, recommendation engines, knowledge graphs. Use Cypher or SPARQL for traversal queries.

Decision guide:
- If data has a schema that evolves unpredictably → Document (schema-on-read).
- If data is highly interconnected with variable relationship types → Graph.
- If data fits rows/columns with strong join needs → Relational.
- Impedance mismatch warning: object-oriented application code + relational DB requires an ORM translation layer. Document databases reduce this impedance for document-centric data.

### Step 6: Select the Query Language

Map the data model to the appropriate query paradigm:

| Data Model | Recommended Language | Key Characteristic |
|---|---|---|
| Relational | SQL | Declarative; optimizer chooses execution plan |
| Document | MongoDB Query API, XQuery | Path-based; nested document traversal |
| Graph | Cypher (Neo4j), SPARQL | Pattern matching across nodes and edges |
| Batch | MapReduce | Functional composition; map + reduce |

Prefer **declarative** over **imperative** query languages when possible — the optimizer can parallelize and optimize without programmer intervention.

## Examples

### Example 1: Twitter-scale fan-out problem

User says: "I'm building a social feed. Every post must appear in followers' timelines. How do I scale this?"

Actions:
1. Identify load parameter: **fan-out factor** (avg. followers per user, distribution skew for celebrities).
2. Two approaches: (a) pull on read — query at read time; (b) push on write — precompute timelines at write time.
3. Recommend hybrid: push-on-write for average users (cheap reads); pull-on-read for high-follower users (avoid 30M write bursts).
4. Quantify: avg tweet → ~75 followers = 345k writes/sec vs 300k read/sec — write amplification is the bottleneck.

Result: A concrete fan-out architecture recommendation with load parameter analysis.

### Example 2: Relational vs. Document for a portfolio project

User says: "My epidemiological data has case records with nested demographic sub-fields. Should I use PostgreSQL or MongoDB?"

Actions:
1. Identify: data is self-contained case records (one-to-many: case → symptoms, contacts).
2. Relationships: limited joins needed between collections.
3. Schema: likely to evolve as new fields emerge.
4. Recommend: Document model (MongoDB) for schema flexibility and locality; but if cross-case analytics with aggregations are needed, consider PostgreSQL with JSONB for hybrid approach.

Result: Justified model selection with trade-off explanation.

### Example 3: Maintainability audit

User says: "Our codebase has grown uncontrollably. How do we think about making it maintainable?"

Actions:
1. Identify accidental complexity: tightly coupled modules, special-case logic, undocumented assumptions.
2. Apply: Simplicity → decompose into well-defined abstractions. Evolvability → ensure new features don't require rewriting existing contracts.
3. Recommend: introduce abstraction layers, enforce schema evolution discipline, add observability before refactoring.

Result: A structured maintainability review with concrete action items.

## Troubleshooting

### Confusion between fault and failure
Cause: User conflates "one node crashed" with "system is down."
Solution: Clarify that a fault is a deviation in one component; a failure is the system no longer serving users. Design so faults are contained and don't cascade into failures.

### "My system is not scalable" without specifics
Cause: Scalability is treated as binary.
Solution: Ask for the specific load parameter under pressure and the resource constraint. Scalability is always relative to a workload profile, not an inherent property.

### Choosing between relational and document without understanding join patterns
Cause: User focuses on schema flexibility alone.
Solution: Ask how the data will be queried. If joins across entities are frequent, the document model creates application-side join complexity that outweighs schema flexibility benefits.
