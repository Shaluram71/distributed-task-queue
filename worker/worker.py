import time
from unittest import result
import psycopg2
from psycopg2 import pool
import redis
import random
import uuid
import threading

redis_client = redis.Redis(
    host = "localhost",
    port = 6379,
    decode_responses=True,
)

#changed single conn connection to a pool to support multiple threads
db_pool = pool.ThreadedConnectionPool(
    1, 
    20,
    host="localhost",
    port=5432,
    dbname="queue",
    user="queue",
    password="queue"
)

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
def heartbeat_thread(job_id, worker_id, interval=30):
    stop_event = threading.Event()
    
    def beat():
        while not stop_event.is_set():
            # borrow and put back connection for each iteration
            heartbeat_conn = db_pool.getconn()
            try:
                with heartbeat_conn.cursor() as cur:
                    cur.execute(
                        """
                        UPDATE jobs
                        SET locked_at = NOW(),
                        locked_by = %s
                        WHERE id = %s
                        """,
                        (worker_id, job_id),
                    )
                    heartbeat_conn.commit()
            except Exception as e:
                print("Heartbeat error for job", job_id, ":", str(e))
                heartbeat_conn.rollback()
            finally:
                db_pool.putconn(heartbeat_conn)

            stop_event.wait(interval)

    thread = threading.Thread(target=beat, daemon=True)
    thread.start()
    return stop_event

#main worker loop
while True:
    release_due_retries(redis_client)
    result = redis_client.brpop("job_queue", timeout=1)
    if not result:
        continue

    _, job_id = result
    worker_id = f"worker-{uuid.uuid4().hex[:8]}"
    print("Picked up job", job_id, "by", worker_id)

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
        (worker_id, job_id,),
        )
        
        if cur.rowcount == 0:
            #another worker has already claimed it
            worker_conn.commit()
            print("Skipped job", job_id, "as it was already claimed")
            continue
        
        worker_conn.commit()
        
    print("Claimed job", job_id)
    heartbeat_stop_event = heartbeat_thread(job_id, worker_id)
    # Simulate job processing
    try:
        print("Processing job", job_id)
        last_char = job_id[-1]
        if last_char.isalpha():
            raise Exception("Simulated job failure")
        with worker_conn.cursor() as cur:
            cur.execute(
            """
            UPDATE jobs
            SET status = 'COMPLETED',
                updated_at = NOW()
            WHERE id = %s
            """,
            (job_id,),
            )
            worker_conn.commit()
        print("Job", job_id, "completed successfully")
        continue
    
    except Exception as e:
        error_message = str(e)
        print("Job", job_id, "failed with error:", error_message)
        with worker_conn.cursor() as cur:
            cur.execute(
                """
                UPDATE jobs
                SET attempts = attempts + 1,
                    error_message = %s,
                    updated_at = NOW()
                WHERE id = %s
                RETURNING attempts, max_attempts
                """,
                (error_message, job_id),
            )
            attempts, max_attempts = cur.fetchone()
            worker_conn.commit()
    
        if attempts < max_attempts:
            with worker_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'PENDING',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                worker_conn.commit()
            
            base_delay = 2  # seconds
            delay = base_delay * (2 ** (attempts - 1))
            jitter = random.uniform(0, delay * .1)
            retry_at = int(time.time() + delay + jitter)
            
            redis_client.zadd("retry_queue", {job_id: retry_at})
            print("Job", job_id, "scheduled to retry in", int(delay + jitter),"seconds (attempt", attempts, "of", max_attempts, ")")
            continue

        else:
            with worker_conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'FAILED',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                worker_conn.commit()
            redis_client.lpush("dead_letter_queue", job_id)
            print("Job", job_id, "has reached max", attempts, "/", max_attempts, ". Sent to dead-letter queue.")
    finally:
        #always return the connection back no matter what
        db_pool.putconn(worker_conn)
        #stop the heartbeat thread
        heartbeat_stop_event.set()