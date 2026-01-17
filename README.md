# Distributed Fault-Tolerant Task Queue

This project implements a distributed task queue inspired by systems like
Celery and AWS SQS, with an emphasis on correctness, failure recovery, and
explicit execution semantics.

## High-Level Architecture
- API service accepts job submissions
- Jobs are persisted in PostgreSQL as the source of truth
- Redis is used for low-latency, event-driven job coordination
- Worker processes execute jobs asynchronously
- Background reaper process detects and recovers abandoned jobs

## Execution & Failure Guarantees
- At-least-once job execution
- Exclusive job ownership via atomic state transitions
- Durable job state tracking in PostgreSQL
- Worker crash tolerance via heartbeat-based liveness detection
- Deterministic recovery of abandoned jobs through reaping

## Current Status
- Job submission via API
- Event-driven worker execution
- Heartbeat-based liveness tracking
- Retry and backoff mechanics
- Reaper implementation present; concurrency semantics under active refinement
