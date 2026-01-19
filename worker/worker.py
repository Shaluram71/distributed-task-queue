import time
from unittest import result
import psycopg2
from psycopg2 import pool, OperationalError
import redis
import random
import uuid
import threading

redis_client = redis.Redis(
    host = "redis",
    port = 6379,
    decode_responses=True,
)

#changed single conn connection to a pool to support multiple threads
def create_db_pool():
    while True:
        try:
            return pool.ThreadedConnectionPool(
                1,
                20,
                host="postgres",
                port=5432,
                dbname="queue",
                user="queue",
                password="queue",
            )
        except OperationalError as e:
            print("Postgres not ready, retrying...", e)
            time.sleep(2)
db_pool = create_db_pool()
#method to release due retries back to job queue
def release_due_retries(redis_client):
    now =  int(time.time())
    
    due_jobs = redis_client.zrangebyscore("retry_queue", min=0, max=now)
    for job_id in due_jobs:
        redis_client.zrem("retry_queue", job_id)
        redis_client.lpush("job_queue", job_id)
        print("Released job", job_id, "from retry queue back to job queue")
print("Worker started... ")

#method to run heartbeat in a separate thread
def heartbeat_thread(job_id, WORKER_ID, interval=30):
    stop_event = threading.Event()
    heart_beat_event = threading.Event()
    def beat():
        while not stop_event.is_set():
            # borrow and put back connection for each iteration
            heart_beat_event.set()
            stop_event.wait(interval)

    thread = threading.Thread(target=beat, daemon=False)
    thread.start()
    return stop_event, heart_beat_event, thread

#main worker loop
WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"
while True:
    release_due_retries(redis_client)
    result = redis_client.brpop("job_queue", timeout=1)
    if not result:
        continue

    _, job_id = result
    
    print("Picked up job", job_id, "by", WORKER_ID)

    # borrowing a connection from the pool
    worker_conn = db_pool.getconn()
    with worker_conn.cursor() as cur:
        cur.execute(
        """
        UPDATE jobs
        SET status = 'IN_PROGRESS',
            locked_by = %s,
            locked_at = NOW(),
            updated_at = NOW()
        WHERE id = %s
            AND status = 'PENDING'
        """,
        (WORKER_ID, job_id,),
        )
        worker_conn.commit()
        
        if cur.rowcount == 0:
            #another worker has already claimed it
            print("Skipped job", job_id, "as it was already claimed")
            db_pool.putconn(worker_conn)
            continue
        
    print("Claimed job", job_id)
    last_heartbeat = time.monotonic()

    heartbeat_stop_event, heartbeat_event, heartbeat_worker_thread = heartbeat_thread(
        job_id, WORKER_ID
    )
    # Simulate job processing
    try:
        print("Processing job", job_id)
        JOB_RUNTIME = 90
        start_run = time.monotonic()
        while time.monotonic() - start_run < JOB_RUNTIME:
            #simulate doing work
            time.sleep(1)
            
            if heartbeat_event.is_set():
                with worker_conn.cursor() as cur:
                    cur.execute(
                    """
                    UPDATE jobs
                    SET locked_at = NOW()
                    WHERE id = %s
                        AND locked_by = %s
                        AND status = 'IN_PROGRESS'
                    """,
                    (job_id, WORKER_ID),
                    )
                    worker_conn.commit()
                heartbeat_event.clear()
                last_heartbeat = time.monotonic()
         
        last_char = job_id[-1]
        if last_char.isalpha():
            raise Exception("Simulated job failure")

        #Success Case
        with worker_conn.cursor() as cur:
            cur.execute(
            """
            UPDATE jobs
            SET status = 'COMPLETED',
                updated_at = NOW(),
                locked_at = NULL,
                locked_by = NULL
            WHERE id = %s
                AND status = 'IN_PROGRESS'
                AND locked_by = %s
            """,
            (job_id, WORKER_ID),
            )
            worker_conn.commit()
        print("Job", job_id, "completed successfully")
    
    except Exception as e:
        error_message = str(e)
        print("Job", job_id, "failed with error:", error_message)
        
        #Failure Case -> check, incerement, and lock in ONE transaction
        with worker_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET attempts = attempts + 1,
                    error_message = %s,
                    updated_at = NOW(),
                    status = CASE 
                        WHEN attempts + 1 >= max_attempts THEN 'FAILED'
                        ELSE 'PENDING'
                    END,
                    locked_at = NULL,
                    locked_by = NULL
                WHERE id = %s
                    AND status = 'IN_PROGRESS'
                    AND locked_by = %s
                RETURNING attempts, max_attempts, status
                """,
                (error_message, job_id, WORKER_ID),
            )
            result = cur.fetchone()
            worker_conn.commit()
    
        if result:
            attempts, max_attempts, status = result
            if status == 'PENDING':
                #schedule for retry with exponential backoff + small jitter
                base_delay = 2 ** (attempts - 1)
                delay = base_delay + (2 ** (attempts - 1))
                jitter = random.uniform(0, delay * .1)
                retry_time = int(time.time() + delay + jitter)
                redis_client.zadd("retry_queue", {job_id: retry_time})
                print("Scheduled job", job_id, "for retry at", retry_time)
            else:
                redis_client.lpush("dead_letter_queue", job_id)
                print("Job", job_id, "moved to dead letter queue after max attempts")
    finally:
        #always return the connection back no matter what
        if heartbeat_stop_event:
            heartbeat_stop_event.set()
        if heartbeat_worker_thread:
            heartbeat_worker_thread.join(timeout=1)
        if worker_conn:
            db_pool.putconn(worker_conn)