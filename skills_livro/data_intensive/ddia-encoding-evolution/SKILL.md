---
name: ddia-encoding-evolution
description: "Applies data encoding and schema evolution principles from Designing Data-Intensive Applications (Kleppmann, Ch.4) to guide serialization format selection and schema compatibility strategies. Use when asked about data formats, serialization, schema evolution, backward/forward compatibility, API versioning, encoding formats (JSON, XML, Protobuf, Avro, Thrift, MessagePack), or rolling upgrades. Trigger phrases: 'how to evolve a schema without breaking clients', 'which serialization format should I use', 'JSON vs Protobuf vs Avro', 'backward compatibility', 'forward compatibility', 'encoding formats trade-offs', 'schema registry', 'rolling upgrade data compatibility'. Do NOT use for storage engine internals (use ddia-storage-retrieval), replication or partitioning (use ddia-replication-partitioning), or stream processing encoding concerns (use ddia-batch-stream-processing)."
license: CC-BY-4.0
metadata:
  author: Roger Quinelato
  version: 1.0.0
---

# DDIA Encoding and Evolution

Guides selection of data encoding formats and schema evolution strategies based on Designing Data-Intensive Applications Ch.4. Covers trade-offs between human-readable and binary formats, schema compatibility modes, and dataflow patterns through services, databases, and message queues.

## Instructions

### Step 1: Clarify the Encoding Context

First, identify where encoding/decoding happens and what the constraints are:

- **In-memory to disk/network**: serialization needed (language-specific or cross-language).
- **Service APIs** (REST/RPC): encoding must support cross-language, versioning, backward/forward compatibility.
- **Database storage**: schema evolution across application versions accessing the same data.
- **Message queues / event streams**: producers and consumers may run different schema versions simultaneously.

### Step 2: Compare Encoding Format Families

**Language-specific formats** (Java Serializable, Python pickle):
- Pros: zero boilerplate within same language.
- Cons: tied to one language, often insecure (arbitrary code execution risk), poor versioning support, poor performance.
- Verdict: avoid for any cross-service or long-lived storage use case.

**Human-readable text formats** (JSON, XML, CSV):
- JSON: ubiquitous, browser-native, schema-optional; no binary support (base64 workaround); no integer/float distinction (JavaScript number precision issue); no schema validation by default.
- XML: verbose, poor binary support, namespace confusion; still standard in banking/enterprise.
- CSV: no type system, no schema, ambiguous delimiter/quoting; useful only for simple tabular exchange.
- Common problem: all three have ambiguous number types, no built-in schema validation, no versioning semantics.

**Binary formats with schema** (Thrift, Protocol Buffers, Avro):

| Format | Schema Required | Schema in Message | Field IDs | Compactness | Best For |
|---|---|---|---|---|---|
| Thrift (BinaryProtocol) | Yes | No | Yes (numeric tags) | Good | Thrift RPC ecosystem |
| Thrift (CompactProtocol) | Yes | No | Yes | Excellent | High-throughput Thrift |
| Protocol Buffers (Protobuf) | Yes | No | Yes (field numbers) | Excellent | gRPC, Google ecosystem |
| Avro | Yes | No (writer/reader schema pair) | No field IDs | Excellent | Hadoop, Kafka, data lakes |
| MessagePack | Optional | Partial | No | Better than JSON | JSON-compatible binary |

### Step 3: Explain Schema Evolution and Compatibility Modes

Compatibility is the ability to evolve a schema without breaking producers or consumers running different versions simultaneously. Two axes:

**Backward Compatibility**: New code (reader) can read data written by old code (writer).
- To maintain: only add new fields with default values. Never remove a required field. Never change a field's data type incompatibly.

**Forward Compatibility**: Old code (reader) can read data written by new code (writer).
- To maintain: old readers must ignore unknown fields. New fields must be optional.

**Full Compatibility**: Both backward AND forward compatibility simultaneously. Required for rolling upgrades of distributed systems.

Protobuf / Thrift rules for compatibility:
- Adding a field: assign a new field number, set it optional → backward + forward compatible.
- Removing a field: only remove optional fields; never reuse the field number.
- Renaming a field: safe (field numbers are the identity, not names).
- Changing a field type: only safe for int32 → int64 (widening); other changes break compatibility.

Avro rules for compatibility (no field numbers):
- Schema matching is by field name, not position.
- Writer schema and reader schema are paired at decode time via a Schema Registry (Confluent, AWS Glue).
- Adding a field: must have a default value → readers without the field use the default.
- Removing a field: only if the field has a default in the reader schema.
- Avro strength: dynamically generated schemas (e.g., from a database column dump) — no manual field ID assignment.

### Step 4: Match Format to Dataflow Type

**Dataflow through databases**:
- Multiple app versions may read/write the same records simultaneously.
- Schema evolution must be backward + forward compatible.
- Recommend: Avro or Protobuf with explicit migration strategy. Avoid adding nullable columns without defaults.
- Pattern: add new field with default → deploy new writers → deploy new readers → then optionally drop old field.

**Dataflow through services (REST / RPC)**:
- REST: JSON + OpenAPI/Swagger for documentation; versioning via URL (/v1/, /v2/) or Accept header.
- gRPC (Protobuf): strongly typed, streaming support, HTTP/2; ideal for internal microservices.
- GraphQL: flexible query shape; client specifies exactly the fields it needs; reduces over-fetching.
- Thrift/Avro RPC: used in Hadoop/Kafka ecosystems.
- Caution with RPC: network calls can fail in ways local function calls cannot (timeout, partial failure). Design with idempotency.

**Dataflow through message queues**:
- Producers and consumers are decoupled — different versions may run simultaneously.
- Schema Registry is essential: Confluent Schema Registry with Avro is the standard for Kafka.
- Enforce compatibility mode at the registry level (BACKWARD, FORWARD, FULL) to prevent incompatible schema registration.

### Step 5: Rolling Upgrade Strategy

When deploying a new schema version to a live system:

1. Phase 1 — New writer schema backward-compatible: deploy new code that can write both old and new format, or writes new format that old readers can still read.
2. Phase 2 — Deploy new readers: all consumers updated to understand the new schema.
3. Phase 3 — Remove old format support: optional cleanup after all writers/readers are updated.

Never deploy a breaking schema change atomically to all nodes simultaneously in a distributed system.

## Examples

### Example 1: Choosing Protobuf vs JSON for microservices

User says: "We have 10 internal microservices talking to each other. Should we use JSON or Protobuf?"

Actions:
1. Identify: internal services, cross-language (Python, Go), high-frequency calls.
2. JSON: human-readable, easy debugging, no schema enforcement by default.
3. Protobuf: 3-10x smaller payload, strongly typed, schema enforcement, gRPC native.
4. For internal high-frequency APIs: recommend gRPC + Protobuf for performance + compatibility guarantees.
5. For external/public APIs: REST + JSON for broad client compatibility.

Result: gRPC + Protobuf for internal; REST + JSON for external.

### Example 2: Schema evolution in Kafka with Avro

User says: "We're adding a new field to our Kafka event schema. How do we do this safely?"

Actions:
1. Confirm Schema Registry is in use (Confluent or compatible).
2. Add new field with a default value in Avro schema.
3. Register new schema — registry validates BACKWARD compatibility.
4. Deploy new producers (they write new field).
5. Old consumers: they deserialize using their old reader schema → new field is ignored via schema resolution.
6. Deploy new consumers: they see the new field.

Result: Zero-downtime rolling schema evolution with no consumer restart required.

### Example 3: Debugging a number precision issue in JSON

User says: "Our JavaScript client is receiving wrong values for large IDs returned from our Python API."

Actions:
1. Identify: JSON has no integer type — JavaScript `Number` is IEEE 754 double (53-bit mantissa).
2. IDs larger than 2^53 lose precision when parsed in JavaScript.
3. Solutions: (a) encode large IDs as strings in JSON; (b) use Protobuf int64 (safe in non-JS clients); (c) use UUID strings instead of sequential integers.

Result: String encoding fix for large integer IDs.

## Troubleshooting

### Avro deserialization fails after schema change
Cause: Writer schema and reader schema are incompatible (field removed without default in reader, or field type changed).
Solution: Check Schema Registry compatibility mode. Add default values to all fields before removing them. Never remove required fields.

### Protobuf field number reuse causing silent data corruption
Cause: A removed field's number was reassigned to a new field of a different type.
Solution: Never reuse field numbers. Mark removed fields as `reserved` in the .proto file. This causes a compile error if the number is accidentally reused.

### JSON schema drift across services
Cause: No schema enforcement — producers add/remove fields without coordinating with consumers.
Solution: Introduce JSON Schema validation at API gateway level, or migrate to Protobuf/Avro with a schema registry enforcing compatibility.
