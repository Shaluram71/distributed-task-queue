import time
import psycopg2
from psycopg2 import pool, OperationalError

HEARTBEAT_INTERVAL = 60
REAPER_INTERAVAL = 30

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
        except OperationalError:
            time.sleep(2)

db_pool = create_db_pool()

print("Reaper started... ")

def reap_stale_jobs():
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, attempts, max_attempts
                FROM jobs
                WHERE status = 'IN_PROGRESS'
                AND locked_at < NOW() - make_interval(secs => %s)
                FOR UPDATE SKIP LOCKED
                """,
                (HEARTBEAT_INTERVAL,),
            )
            
            stale_jobs = cur.fetchall()
        
            for job_id, attemps, max_attemps in stale_jobs:
                if attemps + 1 < max_attemps:
                    cur.execute(
                        '''
                        UPDATE jobs
                        SET status = 'PENDING',
                            locked_at = NULL,
                            locked_by = NULL,
                            attempts = attempts + 1,
                            updated_at = NOW()
                        WHERE id = %s
                        AND status = 'IN_PROGRESS'
                        AND locked_at < NOW() - make_interval(secs => %s)
                        ''',
                        (job_id, HEARTBEAT_INTERVAL,),
                    )
                    print("Reaped stale job", job_id, "back to PENDING")
                else:
                    cur.execute(
                        '''
                        UPDATE jobs
                            SET status = 'FAILED',
                                attempts = attempts + 1,
                                locked_at = NULL,
                                locked_by = NULL,
                                updated_at = NOW()
                            WHERE id = %s
                                AND status = 'IN_PROGRESS'
                                AND locked_at < NOW() - make_interval(secs => %s)
                        ''',
                        (job_id, HEARTBEAT_INTERVAL,),
                    )
                    print("Job", job_id, "has exceeded max attempts. Marked as FAILED")
        conn.commit()
        
    except Exception as e:
        conn.rollback()
        print("Error during reaping stale jobs:", str(e))
    finally:
        db_pool.putconn(conn)

while True:
    reap_stale_jobs()
    time.sleep(REAPER_INTERAVAL)