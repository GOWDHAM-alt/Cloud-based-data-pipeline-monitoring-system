"""
Computes the six quality metrics defined in Section 4 of the contract.
This module only MEASURES — it never decides whether a value is good
or bad. Thresholds and alerting live entirely in Owner A's backend.
"""

from __future__ import annotations

import time
from typing import Any

import pandas as pd


def completeness(df: pd.DataFrame) -> float:
    """Share of non-null values across the whole dataframe, 0 to 1."""
    if df.size == 0:
        return 0.0
    return float(1 - df.isnull().sum().sum() / df.size)


def validity(df: pd.DataFrame, valid_mask: "pd.Series[bool]") -> float:
    """Share of rows passing validation, 0 to 1. Caller supplies the
    boolean mask since 'valid' is domain-specific (business rules)."""
    if len(df) == 0:
        return 0.0
    return float(valid_mask.sum() / len(df))


def uniqueness(df: pd.DataFrame, key_column: str) -> float:
    """Share of unique values in the key column, 0 to 1."""
    if key_column not in df.columns or len(df) == 0:
        return 0.0
    return float(df[key_column].nunique() / len(df))


def timeliness(latest_event_epoch_seconds: float) -> float:
    """Age of the freshest record in seconds (not a 0-1 ratio, per the
    contract's table: 'age of the data in seconds')."""
    return max(0.0, time.time() - latest_event_epoch_seconds)


def schema_consistency(df: pd.DataFrame, expected_columns: list[str]) -> tuple[int, dict[str, Any]]:
    """1 if the schema matches what's expected, else 0, plus details
    about what's missing/extra for the 'details' field."""
    actual = set(df.columns)
    expected = set(expected_columns)
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)
    ok = 1 if not missing and not extra else 0
    details = {}
    if missing:
        details["missing_columns"] = missing
    if extra:
        details["extra_columns"] = extra
    return ok, details


def record_count(df: pd.DataFrame) -> int:
    return int(len(df))


def build_measurements(
    df: pd.DataFrame,
    expected_columns: list[str],
    key_column: str,
    valid_mask: "pd.Series[bool]",
    latest_event_epoch_seconds: float,
) -> list[dict[str, Any]]:
    """Convenience wrapper: builds the full 'measurements' list ready to
    hand to reporter.report_quality(run_id, stage, measurements)."""
    schema_ok, schema_details = schema_consistency(df, expected_columns)

    measurements = [
        {"metric": "completeness", "value": completeness(df)},
        {"metric": "validity", "value": validity(df, valid_mask)},
        {"metric": "uniqueness", "value": uniqueness(df, key_column)},
        {"metric": "timeliness", "value": timeliness(latest_event_epoch_seconds)},
        {"metric": "schema_consistency", "value": schema_ok, "details": schema_details or None},
        {"metric": "record_count", "value": record_count(df)},
    ]
    return measurements
