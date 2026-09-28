"""
The four pipeline stages. Each function does ONE thing and returns a
DataFrame (or writes to storage). No monitoring code lives in here —
instrumentation.instrumented_stage() wraps these from run_pipeline.py.
This keeps the "pipeline still behaves normally if monitoring is off"
guarantee trivially true: these functions don't know monitoring exists.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

from pipeline.data_source import read_source

EXPECTED_COLUMNS = ["order_id", "customer_id", "product", "quantity", "price", "order_date"]


def run_ingestion(source_kind: str, source_path: str) -> pd.DataFrame:
    """Read raw data from CSV, JSON, or an API, as configured."""
    df = read_source(source_kind, source_path)
    return df


def run_transformation(df: pd.DataFrame) -> pd.DataFrame:
    """Clean, type-convert, engineer features, and drop duplicates."""
    df = df.copy()

    # type conversion
    if "quantity" in df.columns:
        df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce")
    if "price" in df.columns:
        df["price"] = pd.to_numeric(df["price"], errors="coerce")
    if "order_date" in df.columns:
        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")

    # data cleaning: strip whitespace from text columns
    for col in df.select_dtypes(include="object").columns:
        df[col] = df[col].astype(str).str.strip()

    # feature engineering
    if {"quantity", "price"}.issubset(df.columns):
        df["order_total"] = df["quantity"] * df["price"]

    # duplicate removal
    dedup_key = "order_id" if "order_id" in df.columns else None
    if dedup_key:
        df = df.drop_duplicates(subset=[dedup_key])
    else:
        df = df.drop_duplicates()

    return df.reset_index(drop=True)


def run_validation(df: pd.DataFrame) -> tuple[pd.DataFrame, "pd.Series[bool]"]:
    """Apply null checks, type checks, schema validation, and business
    rules. Returns the (possibly filtered) dataframe plus a boolean
    mask of which original rows passed, for the 'validity' metric."""
    valid_mask = pd.Series(True, index=df.index)

    # null checks on required fields
    required = ["order_id", "customer_id", "product"]
    for col in required:
        if col in df.columns:
            valid_mask &= df[col].notna()

    # type checks
    if "quantity" in df.columns:
        valid_mask &= df["quantity"].notna() & (df["quantity"] >= 0)
    if "price" in df.columns:
        valid_mask &= df["price"].notna() & (df["price"] >= 0)

    # business rule: order_total should be non-negative if present
    if "order_total" in df.columns:
        valid_mask &= df["order_total"].fillna(0) >= 0

    return df, valid_mask


def run_storage(df: pd.DataFrame, db_path: str, table_name: str = "sales_daily") -> int:
    """Write the processed data to storage. Uses SQLite locally for a
    self-contained demo; swap the connection for PostgreSQL (via
    sqlalchemy/psycopg2) in production per Section 5.5.
    """
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(table_name, conn, if_exists="append", index=False)
        conn.commit()
    finally:
        conn.close()
    return len(df)
