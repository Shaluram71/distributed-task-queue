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
    time.sleep(2)
    
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
        
    print("Completed job", job_id)
   