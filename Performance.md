### Redis-Level Observation (MONITOR)
Using Redis `MONITOR`, the worker was observed issuing one `RPOP job_queue`
command per second while idle. Timestamps confirmed fixed-interval polling,
resulting in continuous Redis traffic even when no jobs were available.

**Observation**
Worker performed ~1 idle poll per second.
This results in ~3600 unnecessary Redis calls per hour per idle worker,
introducing avoidable CPU wakeups and network overhead. This baseline
motivated replacing polling with an event-driven blocking call (`BRPOP`).

## After: Event-Based Worker (BRPOP)
- Worker blocks when idle (no polling)
- Zero Redis calls while idle
- Immediate job pickup on enqueue
- Eliminates sleep-based latency