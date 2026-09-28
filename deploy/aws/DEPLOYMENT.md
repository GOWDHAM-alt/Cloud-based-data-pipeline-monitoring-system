# AWS Deployment — Pipeline & Cloud (Owner B)

Covers Section 5.5 of the contract: hosting, networking, secrets, and
database provisioning for your parts. Owner A hosts the backend API
and dashboard the same way; this doc only covers your pieces (pipeline
runner + metrics agent) plus the shared database.

## 1. Services used

| Need | Service | Notes |
|---|---|---|
| Run the pipeline on a schedule | **ECS Fargate** (scheduled task) or **EventBridge Scheduler + Fargate task** | No servers to patch; pipeline runs, reports, exits |
| Run the metrics agent continuously | **ECS Fargate** (long-running service, desired count 1) | Always-on, separate task definition from the pipeline |
| Database (owned by Owner A, provisioned by you per Section 5.5) | **RDS for PostgreSQL** | Single-AZ is fine for a student/demo project; keep off the public internet |
| Secrets | **AWS Secrets Manager** | `MONITOR_API_KEY`, `DATABASE_URL`, any other credentials |
| Networking | **VPC** with private subnets for the DB and tasks, a NAT gateway only if the pipeline needs outbound internet (e.g. an API data source) | Backend/dashboard get their own public-facing setup from Owner A |
| Health checks | ECS health check hitting the backend's `GET /health` | Confirms the backend is reachable before the pipeline task is considered healthy |
| Metrics / logs | **CloudWatch Logs** for task stdout, **CloudWatch Alarms** optionally on task failures | Free tier is enough for this project |

## 2. Networking

1. Create a VPC with at least two private subnets (different AZs) and one public subnet if you need a NAT gateway for outbound calls (e.g. `PIPELINE_DATA_SOURCE=api`).
2. Put the RDS instance in the private subnets, with a security group that allows inbound Postgres (5432) **only** from the backend's and pipeline's security groups — never from `0.0.0.0/0`.
3. Give the pipeline and metrics-agent ECS tasks a security group that allows outbound HTTPS to the backend's address (and to the internet if the NAT gateway is present).
4. The backend and dashboard (Owner A's) get their own public-facing setup (ALB, etc.) — you only need to know their reachable base URL to set `MONITOR_API_URL`.

## 3. Database provisioning (your responsibility per Section 5.5)

```
aws rds create-db-instance \
  --db-instance-identifier monitoring-db \
  --db-instance-class db.t4g.micro \
  --engine postgres \
  --engine-version 16 \
  --master-username <set-via-secrets-manager> \
  --master-user-password <set-via-secrets-manager> \
  --allocated-storage 20 \
  --vpc-security-group-ids <db-sg-id> \
  --db-subnet-group-name <private-subnet-group> \
  --no-publicly-accessible \
  --backup-retention-period 1
```

Hand the resulting `DATABASE_URL` (or host/port/db name) to Owner A — the schema itself is their responsibility, not yours.

## 4. Secrets

Store these in Secrets Manager, never in git or `.env.example`:

- `MONITOR_API_KEY`
- `DATABASE_URL`
- any data-source credentials (e.g. an API key if `PIPELINE_DATA_SOURCE=api`)

ECS task definitions reference secrets by ARN under `secrets`, not `environment`, so they're injected at runtime rather than baked into the image or visible in `describe-task-definition` in plaintext.

## 5. ECS task definitions (outline)

Two separate task definitions, both built from images pushed to ECR:

- `pipeline-runner`: from `deploy/Dockerfile.pipeline`. Triggered by an EventBridge Scheduler rule (e.g. every hour, or matching whatever cadence `sales_daily` implies) rather than running continuously.
- `metrics-agent`: from `deploy/Dockerfile.agent`. An ECS Service with `desiredCount: 1` so it's always running and self-heals if the task dies.

Both get `MONITOR_API_URL`, `MONITORING_ENABLED`, `METRICS_INTERVAL_SECONDS` as plain environment variables (not secret), and `MONITOR_API_KEY` / `DATABASE_URL` injected from Secrets Manager.

## 6. CI/CD hook-in

The GitHub Actions workflow (`.github/workflows/ci-cd.yml`) builds and pushes both images to ECR on merge to `main`, then updates the ECS task definitions to the new image tag and forces a new deployment. See that file for the exact steps.

## 7. Health checks

Point your pipeline and agent tasks' dependency check at the backend's `GET /health` before considering a deploy successful — if the backend isn't reachable yet, retries in the reporter client will handle transient failures, but a completely wrong `MONITOR_API_URL` should fail fast in CI rather than silently in production.

## 8. What you hand to Owner A per environment

- The deployed base URL and API key are Owner A's to hand to *you* (since they own the backend) — what you hand back is:
  - Confirmation the pipeline and metrics agent are deployed and reporting
  - The RDS endpoint, if you provisioned it
  - Your CloudWatch log group names, in case they need to help debug a reporting issue from your side

## 9. Cost awareness (student project)

- `db.t4g.micro` RDS + Fargate with minimal vCPU/memory for both tasks stays within or close to AWS free-tier/cheap-tier limits for a few months of a final-year project.
- Stop/delete the RDS instance and scale the metrics-agent service to 0 when not actively working, to avoid ongoing charges.
