# Distributed Fault-Tolerant Task Queue
This project implements a distributed task queue inspired by systems like
Celery and AWS SQS.

# High-Level Architecture
- API service accepts job submissions
- Jobs are persisted in Postgres (source of truth)
- Redis is used as a fast coordination queue
- Worker processes execute jobs asynchronously

# Guarantees
- At-least-once job execution
- Durable job state tracking
- Worker crash tolerance (iterative)

## Current Status
- Submit job
- Enqueue job
- Worker executes job
