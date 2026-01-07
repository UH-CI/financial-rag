
from redis import Redis
from rq import Queue
from rq.registry import FailedJobRegistry, StartedJobRegistry

redis_conn = Redis(host='redis', port=6379, db=0)
q = Queue(connection=redis_conn)

print(f"Queue size: {len(q)}")
print(f"Job IDs in queue: {q.job_ids}")

registry = StartedJobRegistry(queue=q)
print(f"Jobs currently running: {registry.get_job_ids()}")

failed_registry = FailedJobRegistry(queue=q)
print(f"Failed jobs: {failed_registry.get_job_ids()}")

for job_id in failed_registry.get_job_ids():
    job = q.fetch_job(job_id)
    if job:
        print(f"--- Failed Job {job_id} ---")
        print(f"Exc info: {job.exc_info}")
