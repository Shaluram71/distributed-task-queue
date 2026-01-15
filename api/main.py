from fastapi import FastAPI, Body
from pydantic import BaseModel
from typing import Any, Dict
import psycopg2
from psycopg2.extras import Json
import uuid
import redis

app = FastAPI()
class JobCreateRequest(BaseModel):
    payload: Dict[str, Any]
    max_attempts: int

@app.post("/jobs")
def create_job(job: JobCreateRequest = Body(...)):
    job_id = str(uuid.uuid4())
    
    with conn.cursor() as cur:
        cur.execute(
    """
    INSERT INTO jobs (
        id,
        payload,
        status,
        attempts,
        max_attempts
    )
    VALUES (%s, %s, %s, %s, %s)
    """,
    (
        job_id,
        Json(job.payload),
        "PENDING",
        0,
        job.max_attempts,
    ),
                )

        conn.commit()
    
    redis_client.lpush("job_queue", job_id)

    return {"job_id": job_id }

# database connection
conn = psycopg2.connect(
    host = "localhost",
    port=5432,
    dbname = "queue",
    user = "queue",
    password = "queue",
)

#redis connection
redis_client = redis.Redis(
    host='localhost',
    port=6379, 
    decode_responses=True
    )