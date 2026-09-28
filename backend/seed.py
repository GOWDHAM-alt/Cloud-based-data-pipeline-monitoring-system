import json
import random
import uuid
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

BASE = "http://localhost:8001/api/v1"
KEY = "devkey123"
STAGES = ["ingestion", "transformation", "validation", "storage"]


def send(path, body, method="POST"):
    req = Request(
        BASE + path,
        data=json.dumps(body).encode(),
        method=method,
        headers={"Content-Type": "application/json", "X-API-Key": KEY},
    )
    urlopen(req, timeout=10).read()


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


now = datetime.now(timezone.utc)

for i in range(8):
    run_id = str(uuid.uuid4())
    start = now - timedelta(hours=8 - i)
    fail_stage = "storage" if i in (3, 6) else None

    send("/runs", {
        "run_id": run_id,
        "pipeline": "seed_demo",
        "started_at": iso(start),
        "metadata": {"trigger": "seed"},
    })

    t = start
    for s in STAGES:
        end = t + timedelta(seconds=random.randint(20, 60))
        failed = s == fail_stage
        send(f"/runs/{run_id}/stages", {
            "stage": s,
            "status": "failed" if failed else "success",
            "started_at": iso(t),
            "ended_at": iso(end),
            "records_in": 10000,
            "records_out": 0 if failed else random.randint(9900, 10000),
            "error_message": "Connection to target database timed out" if failed else None,
        })
        if s == "validation":
            send(f"/runs/{run_id}/quality", {
                "stage": "validation",
                "measurements": [
                    {"metric": "completeness", "value": round(random.uniform(0.93, 1.0), 3)},
                    {"metric": "schema_consistency", "value": 1},
                ],
            })
        if failed:
            send(f"/runs/{run_id}/events", {
                "level": "error",
                "stage": s,
                "message": "Connection to target database timed out",
                "timestamp": iso(end),
            })
            t = end
            break
        t = end

    send(f"/runs/{run_id}", {
        "status": "failed" if fail_stage else "success",
        "ended_at": iso(t),
        "records_in": 10000,
        "records_out": 0 if fail_stage else 9950,
    }, method="PATCH")

print("Seeded 8 runs")