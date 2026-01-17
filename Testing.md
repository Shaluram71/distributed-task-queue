## Validation & Failure Testing

System behavior was validated through targeted manual testing and failure injection, with a focus on correctness guarantees, lifecycle invariants, and behavior under partial failure. Testing prioritized observability and deterministic recovery over early test automation.

### 1. Job Lifecycle & Ownership

- Submitted sample jobs through the application interface
- Verified exclusive job claiming using conditional updates (`PENDING → IN_PROGRESS`)
- Confirmed correct lifecycle transitions:
  - `PENDING → IN_PROGRESS → COMPLETED`
  - `PENDING → IN_PROGRESS → FAILED`
- Ensured database connections were correctly borrowed and returned after execution

This validated single-worker ownership and baseline execution correctness.

### 2. Worker Heartbeat & Liveness Tracking

- Executed long-running jobs exceeding the heartbeat interval
- Observed periodic updates to the `locked_at` column while jobs were in progress
- Verified heartbeat updates were isolated from job execution and stopped immediately upon reaching a terminal state

This confirmed reliable liveness signaling independent of execution paths.

### 3. Failure Injection & Retry Semantics

- Injected deterministic job failures during execution
- Verified:
  - attempt counters incremented correctly
  - error metadata was persisted
  - retryable jobs transitioned back to `PENDING`
  - retries were scheduled using exponential backoff with jitter

This ensured failure handling was predictable and non-destructive.

### 4. Worker Crash Simulation
- Terminated the worker process mid-execution using `Ctrl+C`
- Verified affected jobs remained in `IN_PROGRESS`
- Observed that heartbeat updates (`locked_at`) ceased immediately after termination
- Confirmed no automatic retry or failure transition occurred without explicit recovery

This validated that unexpected worker termination leaves behind a detectable and recoverable state rather than corrupting job lifecycle.


### 5. State Observability & Recovery Signals

- Inspected job state directly via SQL queries against the `jobs` table
- Used `status`, `locked_at`, `updated_at`, and attempt counters to reason about system behavior
- Confirmed that abandoned jobs are identifiable as:
  - `status = 'IN_PROGRESS'` with a stale `locked_at` timestamp

These signals form the basis for deterministic recovery via a reaper process.


### Summary
These validations confirmed that the system:
- enforces exclusive job ownership
- tracks worker liveness independently and reliably
- handles retryable and terminal failures deterministically
- exposes abandoned jobs explicitly for recovery

Observations from failure testing directly informed the design of heartbeat semantics and the job reaper.
