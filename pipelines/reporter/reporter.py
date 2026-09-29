"""
MonitorReporter — the reporter client described in Section 5.2 of the
pipeline/cloud contract.

Design rules this module must never break:
  1. It must NEVER raise an exception into the pipeline. Every public
     method catches everything internally and logs instead.
  2. When MONITORING_ENABLED=false, every method is a no-op. This is
     the switch that makes the Phase 6 overhead comparison possible.
  3. Requests are short-timeout, retried a few times on server errors,
     and never retried on 422 (that means our payload is wrong).
"""

from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any, Optional
from datetime import datetime, timezone
import requests

logger = logging.getLogger("monitor_reporter")

DEFAULT_TIMEOUT_SECONDS = 3
DEFAULT_MAX_RETRIES = 3
DEFAULT_RETRY_DELAY_SECONDS = 1.0


def _env_bool(name: str, default: bool) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in ("1", "true", "yes", "on")


class MonitorReporter:
    """Client the pipeline uses to send run, stage, quality and log
    events to the backend API. See Section 4 of the contract for the
    exact payload shapes.
    """

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        enabled: Optional[bool] = None,
        timeout: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        retry_delay: float = DEFAULT_RETRY_DELAY_SECONDS,
    ):
        self.base_url = (base_url or os.getenv("MONITOR_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("MONITOR_API_KEY", "")
        self.enabled = enabled if enabled is not None else _env_bool("MONITORING_ENABLED", True)
        self.timeout = timeout
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._session = requests.Session()

        if self.enabled and not self.base_url:
            logger.warning(
                "MONITORING_ENABLED is true but MONITOR_API_URL is not set; "
                "reporting calls will fail and be logged, but the pipeline will continue."
            )

    # ------------------------------------------------------------------ #
    # internal transport
    # ------------------------------------------------------------------ #
    def _request(self, method: str, path: str, json_body: dict) -> Optional[dict]:
        """POST/PATCH a payload. Returns the parsed JSON response, or
        None if the call was skipped or ultimately failed. Never raises.
        """
        if not self.enabled:
            return None

        url = f"{self.base_url}{path}"
        headers = {"X-API-Key": self.api_key, "Content-Type": "application/json"}

        attempt = 0
        while attempt <= self.max_retries:
            attempt += 1
            try:
                resp = self._session.request(
                    method, url, json=json_body, headers=headers, timeout=self.timeout
                )
            except requests.exceptions.RequestException as exc:
                logger.warning(
                    "Monitor API request failed (attempt %s/%s) %s %s: %s",
                    attempt, self.max_retries + 1, method, url, exc,
                )
                if attempt > self.max_retries:
                    return None
                time.sleep(self.retry_delay)
                continue

            if resp.status_code == 422:
                # Our payload is wrong. Log it and do NOT retry.
                logger.error(
                    "Monitor API rejected payload (422) %s %s: %s | body=%s",
                    method, url, resp.text, json_body,
                )
                return None

            if 200 <= resp.status_code < 300:
                try:
                    return resp.json()
                except ValueError:
                    return None

            # 5xx or other server-side problem: retry.
            logger.warning(
                "Monitor API returned %s (attempt %s/%s) %s %s",
                resp.status_code, attempt, self.max_retries + 1, method, url,
            )
            if attempt > self.max_retries:
                return None
            time.sleep(self.retry_delay)

        return None

    # ------------------------------------------------------------------ #
    # public API — mirrors Section 5.2 exactly
    # ------------------------------------------------------------------ #
    def start_run(self, pipeline: str, metadata: Optional[dict] = None) -> str:
        """Generates a run_id, tells the backend a run has started, and
        returns the run_id regardless of whether the API call succeeded
        (the pipeline must be able to proceed either way).
        """
        run_id = str(uuid.uuid4())
        if not self.enabled:
            return run_id

        payload = {
            "run_id": run_id,
            "pipeline": pipeline,
            "started_at": _now_iso(),
            "metadata": metadata or {},
        }
        self._request("POST", "/api/v1/runs", payload)
        return run_id

    def report_stage(
        self,
        run_id: str,
        stage: str,
        status: str,
        started_at: str,
        ended_at: str,
        records_in: Optional[int] = None,
        records_out: Optional[int] = None,
        error_message: Optional[str] = None,
    ) -> None:
        payload = {
            "stage": stage,
            "status": status,
            "started_at": started_at,
            "ended_at": ended_at,
            "records_in": records_in,
            "records_out": records_out,
            "error_message": error_message,
        }
        self._request("POST", f"/api/v1/runs/{run_id}/stages", payload)

    def report_quality(self, run_id: str, stage: str, measurements: list[dict[str, Any]]) -> None:
        payload = {"stage": stage, "measurements": measurements}
        self._request("POST", f"/api/v1/runs/{run_id}/quality", payload)

    def log_event(self, run_id: str, level: str, stage: str, message: str) -> None:
        payload = {
            "level": level,
            "stage": stage,
            "message": message,
            "timestamp": _now_iso(),
        }
        self._request("POST", f"/api/v1/runs/{run_id}/events", payload)

    def finish_run(
        self,
        run_id: str,
        status: str,
        records_in: Optional[int] = None,
        records_out: Optional[int] = None,
    ) -> None:
        payload = {
            "status": status,
            "ended_at": _now_iso(),
            "records_in": records_in,
            "records_out": records_out,
        }
        self._request("PATCH", f"/api/v1/runs/{run_id}", payload)

    def report_infra_metrics(
        self,
        host: str,
        cpu_percent: float,
        memory_percent: float,
        run_id: Optional[str] = None,
    ) -> None:
        payload = {
            "host": host,
            "timestamp": _now_iso(),
            "cpu_percent": cpu_percent,
            "memory_percent": memory_percent,
        }
        if run_id:
            payload["run_id"] = run_id
        self._request("POST", "/api/v1/metrics/infra", payload)


def now_iso() -> str:
    """UTC timestamp in the ISO 8601 'Z' format the contract requires."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")

# kept as an alias since earlier drafts of this module used a leading
# underscore; other modules should prefer now_iso().
_now_iso = now_iso
