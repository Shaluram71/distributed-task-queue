# Distributed Task Queue — Design Decisions
This document explains the key design decisions behind the task queue system
and the tradeoffs considered for each choice.

## Job Table Schema
The schema is designed to support exclusive job ownership, crash detection,
and deterministic recovery through persisted state rather than worker memory.

### `id` — UUID
**Choice:** UUID  

**Why:**
- Ensures global uniqueness across distributed workers
- Avoids coordination required by auto-increment IDs
- Common in distributed job systems

**Tradeoffs:**
- Slightly larger than integers
- Acceptable given low write volume

### 'attempts' - INT
`attempts` represents the number of execution attempts that have reached a terminal failure.

### `payload` — JSONB
**Choice:** `JSONB` instead of `TEXT` or `JSON`

**Why:**
- Job payloads are structured data, not opaque strings
- Formatting and key order do not matter
- Jobs may be retried and inspected multiple times
- JSONB is parsed once on write, making repeated reads faster

**Tradeoffs:**
- Slightly slower writes than JSON
- Acceptable since reads and queries dominate

**Rejected Alternatives:**
- `TEXT`: loses structure and queryability
- `JSON`: slower reads and limited indexing

### `status` — TEXT with Constraints
**Choice:** `TEXT` with application-level constraints  

**Initial states:** `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`

**Why:**
- ENUMs are difficult to modify in Postgres
- New states may be added as the system evolves
- TEXT + constraints offers flexibility while preserving correctness, allowing the lifecycle to evolve without schema migrations.

**Tradeoffs:**
- Less strict than ENUM at the database level
- Mitigated by application-level validation

### Removed Field: `hasRun`

**Reason for removal:**
- Redundant with `status`
- Could become inconsistent (e.g. `hasRun = false` but `status = COMPLETED`)
- Derived values should not be stored directly

**Principle Applied:**
- Do not store data that can be derived from other columns

### `error_message` — TEXT (Nullable)
**Choice:** Store only the most recent error

**Why:**
- Simpler than storing an array of errors
- Sufficient for debugging and retries
- Avoids premature complexity

**Future Improvements:**
- Separate error log table
- Structured error metadata

## SQL Query for Table:

CREATE TABLE jobs (
    id UUID PRIMARY KEY,
    payload JSONB NOT NULL,

    status TEXT NOT NULL CHECK (
        status IN ('PENDING', 'IN_PROGRESS', 'COMPLETED', 'FAILED')
    ),

    attempts INTEGER NOT NULL DEFAULT 0,
    max_attempts INTEGER NOT NULL,

    error_message TEXT,

    created_at TIMESTAMP NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP NOT NULL DEFAULT NOW()
);

## Schema Validation Notes

- Verified that valid job states are accepted
- Invalid states are rejected by database constraints
- Default values and timestamps behave as expected
