import os

from dotenv import load_dotenv

load_dotenv()

MONITOR_API_URL = os.getenv("MONITOR_API_URL", "http://localhost:8001")
MONITOR_API_KEY = os.getenv("MONITOR_API_KEY", "changeme")
MONITORING_ENABLED = os.getenv("MONITORING_ENABLED", "true").lower() in ("1", "true", "yes")
METRICS_INTERVAL_SECONDS = float(os.getenv("METRICS_INTERVAL_SECONDS", "10"))
METRICS_HOST_NAME = os.getenv("METRICS_HOST_NAME", "worker-1")

PIPELINE_DATA_SOURCE = os.getenv("PIPELINE_DATA_SOURCE", "csv")  # csv | json | api
PIPELINE_SOURCE_PATH = os.getenv("PIPELINE_SOURCE_PATH", "data/sample_sales.csv")
PIPELINE_NAME = os.getenv("PIPELINE_NAME", "sales_daily")
