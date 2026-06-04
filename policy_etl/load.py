"""Load transformed datasets to Parquet and SQLite."""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

from policy_etl.config import PipelineConfig

logger = logging.getLogger(__name__)


def _write_parquet(df: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(path, index=False)


def load_parquet_artifacts(config: PipelineConfig, artifacts: dict[str, Any]) -> None:
    warehouse = config.warehouse_dir
    warehouse.mkdir(parents=True, exist_ok=True)

    for name, frame in artifacts["dimensions"].items():
        _write_parquet(frame, warehouse / f"{name}.parquet")

    _write_parquet(artifacts["fact_policy_events"], warehouse / "fact_policy_events.parquet")
    _write_parquet(artifacts["mart_policy_status"], warehouse / "mart_policy_status.parquet")
    _write_parquet(artifacts["mart_renewals_daily"], warehouse / "mart_renewals_daily.parquet")

    if len(artifacts["quarantine"]) > 0:
        config.quarantine_dir.mkdir(parents=True, exist_ok=True)
        _write_parquet(
            artifacts["quarantine"],
            config.quarantine_dir / "quarantined_events.parquet",
        )

    logger.info("Wrote Parquet artifacts to %s", warehouse)


def load_sqlite(config: PipelineConfig, artifacts: dict[str, Any]) -> None:
    config.warehouse_dir.mkdir(parents=True, exist_ok=True)
    if config.sqlite_path.exists():
        config.sqlite_path.unlink()

    conn = sqlite3.connect(config.sqlite_path)
    try:
        for name, frame in artifacts["dimensions"].items():
            frame.to_sql(name, conn, index=False, if_exists="replace")

        artifacts["fact_policy_events"].to_sql(
            "fact_policy_events", conn, index=False, if_exists="replace"
        )
        artifacts["mart_policy_status"].to_sql(
            "mart_policy_status", conn, index=False, if_exists="replace"
        )
        artifacts["mart_renewals_daily"].to_sql(
            "mart_renewals_daily", conn, index=False, if_exists="replace"
        )

        conn.executescript(
            """
            CREATE INDEX IF NOT EXISTS idx_fact_event_type ON fact_policy_events(event_type);
            CREATE INDEX IF NOT EXISTS idx_fact_event_date ON fact_policy_events(event_date);
            CREATE INDEX IF NOT EXISTS idx_fact_product_type ON fact_policy_events(product_type);
            CREATE INDEX IF NOT EXISTS idx_mart_status ON mart_policy_status(status);
            CREATE INDEX IF NOT EXISTS idx_mart_renewals_date ON mart_renewals_daily(event_date);
            """
        )
        conn.commit()
    finally:
        conn.close()

    logger.info("Loaded SQLite warehouse at %s", config.sqlite_path)


def load_all(config: PipelineConfig, artifacts: dict[str, Any]) -> None:
    load_parquet_artifacts(config, artifacts)
    load_sqlite(config, artifacts)
