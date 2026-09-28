"""
Ingestion sources. All three return a pandas DataFrame so downstream
stages don't care which source was used.
"""

from __future__ import annotations

import json

import pandas as pd
import requests


def read_csv_source(path: str) -> pd.DataFrame:
    return pd.read_csv(path)


def read_json_source(path: str) -> pd.DataFrame:
    with open(path, "r") as f:
        data = json.load(f)
    return pd.DataFrame(data)


def read_api_source(url: str, timeout: float = 10.0) -> pd.DataFrame:
    resp = requests.get(url, timeout=timeout)
    resp.raise_for_status()
    return pd.DataFrame(resp.json())


def read_source(kind: str, path_or_url: str) -> pd.DataFrame:
    if kind == "csv":
        return read_csv_source(path_or_url)
    if kind == "json":
        return read_json_source(path_or_url)
    if kind == "api":
        return read_api_source(path_or_url)
    raise ValueError(f"Unknown data source kind: {kind}")
