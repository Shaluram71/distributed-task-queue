from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Any, Dict
import psycopg2
from psycopg2 import pool
from psycopg2.extras import Json
import uuid
import redis
import time

app = FastAPI()

@app.on_event("startup")
def startup_event():
    global db_pool, redis_client
    while True:
        try:
            db_pool = pool.ThreadedConnectionPool(
                minconn=1,
                maxconn=10,   # API: concurrent requests
                host="postgres",
                port=5432,
                dbname="queue",
                user="queue",
                password="queue",
            )
            redis_client = redis.Redis(
                host='redis',
                port=6379, 
                decode_responses=True,
            )
            redis_client.ping()
            print("API connected to Postgres and Redis")
            break
        except Exception as e:
            print("Connections not ready, retrying...", e)
            time.sleep(1)

class JobCreateRequest(BaseModel):
    payload: Dict[str, Any]
    max_attempts: int

@app.post("/jobs")
def create_job(job: JobCreateRequest = Body(...)):
    job_id = str(uuid.uuid4())
    conn = db_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute(
        """
        INSERT INTO jobs (
            id,
            payload,
            max_attempts
        )
        VALUES (%s, %s, %s)
        """,
        (job_id, Json(job.payload), job.max_attempts),
    )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        db_pool.putconn(conn)
    redis_client.lpush("job_queue", job_id)
    return {"job_id": job_id }