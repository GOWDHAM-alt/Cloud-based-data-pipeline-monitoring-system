# Pipeline & Cloud — Owner B's side

Implements the modules owned by Owner B per `PIPELINE_CLOUD_PLAN.md`:
pipeline (ingestion → transformation → validation → storage), reporter
client, metrics agent, fault injection, cloud deployment, and the
monitoring-overhead measurement. Owner A's backend API, database
schema, alert rules, and dashboard are **not** included here — this
side only talks to them over the HTTP contract in Section 4 of the
plan.

All of this has been run and verified end-to-end against the mock API
server included here (`pipelines/tools/mock_server.py`).

## Layout

```
pipelines/
├── pipeline/       # Module 1 — ingestion, transformation, validation, storage
├── reporter/        # Module 2 — MonitorReporter client
├── agent/            # Module 6 — CPU/memory metrics agent
├── faults/           # Module 8 — fault injection scenarios
├── tools/             # mock API server, for testing before the real backend exists
├── data/                # sample data generator + local sqlite "warehouse"
└── requirements.txt
deploy/                 # Module 9/10 — Dockerfiles, docker-compose, AWS deployment guide
.github/workflows/       # Module 11 — CI/CD
performance/             # Module 12 — monitoring on/off overhead comparison
```

## Quickstart

```bash
cd pipelines
pip install -r requirements.txt --break-system-packages   # or use a venv
cp .env.example .env
python data/generate_sample_data.py

# terminal 1 — mock API server, standing in for Owner A's backend
uvicorn tools.mock_server:app --port 8001

# terminal 2 — run the pipeline once
PYTHONPATH=. python -m pipeline.run_pipeline

# terminal 3 — metrics agent, runs continuously
PYTHONPATH=. python -m agent.metrics_agent
```

Inspect a run directly from the mock server:
```bash
curl http://localhost:8001/api/v1/runs/<run_id>
```

## Fault injection

```bash
PYTHONPATH=. python -m faults.fault_injector null_spike
PYTHONPATH=. python -m faults.fault_injector dropped_column
PYTHONPATH=. python -m faults.fault_injector delayed_source
PYTHONPATH=. python -m faults.fault_injector stage_crash
PYTHONPATH=. python -m faults.fault_injector all
```

Every injected fault is appended to `pipelines/faults/injected_faults.log`
as `{fault_type, injected_at, run_id}` — hand this to Owner A to compute
alert precision/recall.

## Overhead measurement (Phase 6)

```bash
cd performance
python overhead_test.py --runs 20 --cwd ../pipelines
```

This launches the pipeline as a subprocess and samples its own CPU/RSS
with `psutil` while it runs — measured independently of the API, since
the API receives nothing when `MONITORING_ENABLED=false`. Raw numbers
land in `overhead_results.csv`; only those measured values should go
in the paper's results table.

## Switching from the mock server to the real backend

Once Owner A's API is running locally (with `/docs` available), change
one line in `.env`:
```
MONITOR_API_URL=http://localhost:<their-port>
```
Nothing else changes — that's the point of the contract boundary.

## Deployment

See `deploy/aws/DEPLOYMENT.md` for the full AWS setup (ECS Fargate for
the pipeline + metrics agent, RDS for Postgres, Secrets Manager, VPC).
`deploy/docker-compose.yml` runs the pipeline, metrics agent, and mock
API together locally for integration testing.

## CI/CD

`.github/workflows/ci-cd.yml` runs the pipeline and all four fault
scenarios against the mock API on every push, then on merge to `main`
builds and pushes Docker images to ECR and redeploys the ECS services.
Requires these repo secrets: `AWS_DEPLOY_ROLE_ARN`, `AWS_REGION`,
`ECS_CLUSTER_NAME`.

## What's still an open decision (Section 10 of the plan)

- Whether to move off a plain Python script to Airflow later
- Final data source/volume for the real (non-sample) pipeline
- Cloud provider confirmation (this repo assumes AWS)
- Final run count / metrics interval for the overhead test — the
  numbers above were 3-run smoke tests, not the real experiment
