## Baseline: Polling-Based Worker Behavior

Using Redis `MONITOR`, idle workers were observed issuing one `RPOP job_queue`
command per second. Timestamped command logs confirmed fixed-interval polling,
resulting in continuous Redis traffic even when no jobs were available.

### Observations
- ~1 Redis call per second per idle worker
- ~3,600 unnecessary Redis calls per hour per worker
- Continuous CPU wakeups and network traffic while idle

This baseline demonstrated avoidable overhead and motivated a transition to
event-driven queue consumption.

## Event-Driven Worker (BRPOP)

Workers were migrated to use Redis `BRPOP`, enabling blocking behavior when the
queue is empty.

### Results
- Zero Redis calls while idle
- Immediate job pickup on enqueue
- Elimination of sleep-based latency and polling overhead

A short `BRPOP` timeout is used to allow periodic release of delayed retries
without reintroducing busy polling.

## Retry Backoff Strategy

Immediate retries can cause retry storms and amplify load during failure
conditions. To mitigate this, retries use exponential backoff, consistent with
production systems such as SQS, Celery, and Sidekiq.

A small randomized jitter was added to retry delays to prevent synchronized
retries (thundering herd behavior). Given the well-understood tradeoffs,
exponential backoff was adopted directly rather than benchmarking immediate
retry strategies.
