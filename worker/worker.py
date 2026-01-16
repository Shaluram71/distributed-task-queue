import time
import psycopg2
import redis

redis_client = redis.Redis(
    host = "localhost",
    port = 6379,
    decode_responses=True,
)

conn = psycopg2.connect(
    host = "localhost",
    port=5432,
    dbname = "queue",
    user = "queue",
    password = "queue",
)

print("Worker started... ")

while True:
    job_id = redis_client.rpop("job_queue")
    
    if job_id is None:
        time.sleep(1)
        continue
    with conn.cursor() as cur:
        cur.execute(
        """
        UPDATE jobs
        SET status = 'IN_PROGRESS',
            updated_at = NOW()
        WHERE id = %s
            AND status = 'PENDING'
        """,
        (job_id,),
        )
        
        if cur.rowcount == 0:
            #another worker has already claimed it
            conn.commit()
            print("Skipped job", job_id, "as it was already claimed")
            continue
        
        conn.commit()
        
    print("Claimed job", job_id)

    # Simulate job processing
    try:
        print("Processing job", job_id)
        last_char = job_id[-1]
        if last_char.isalpha():
            raise Exception("Simulated job failure")
        with conn.cursor() as cur:
            cur.execute(
            """
            UPDATE jobs
            SET status = 'COMPLETED',
                updated_at = NOW()
            WHERE id = %s
            """,
            (job_id,),
            )
            conn.commit()
        print("Job", job_id, "completed successfully")
        continue
    
    except Exception as e:
        error_message = str(e)
        print("Job", job_id, "failed with error:", error_message)
        with conn.cursor() as cur:
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
            conn.commit()
        if attempts < max_attempts:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'PENDING',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                conn.commit()
            print("Re-queuing job", job_id, "for retry", attempts, "of", max_attempts)
            redis_client.lpush("job_queue", job_id)
        else:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = 'FAILED',
                        updated_at = NOW()
                    WHERE id = %s
                    """,
                    (job_id,),
                )
                conn.commit()
            redis_client.lpush("dead_letter_queue", job_id)
            print("Job", job_id, "has reached max", attempts, "/", max_attempts, ". Sent to dead-letter queue.")
        continue