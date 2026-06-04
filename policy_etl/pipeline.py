"""Orchestrate extract, transform, and load."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Any

import pandas as pd

from policy_etl.config import PipelineConfig
from policy_etl.extract import extract_raw_events
from policy_etl.load import load_all
from policy_etl.transform import transform

logger = logging.getLogger(__name__)


@dataclass
class PipelineResult:
    run_id: str
    raw_row_count: int
    clean_row_count: int
    quarantine_row_count: int
    output_dir: str


def run_pipeline(config: PipelineConfig) -> tuple[PipelineResult, dict[str, Any]]:
    run_id = config.run_id or uuid.uuid4().hex[:12]
    config.staging_dir.mkdir(parents=True, exist_ok=True)

    logger.info("Starting pipeline run %s", run_id)
    raw = extract_raw_events(config.input_dir)

    staging_path = config.staging_dir / f"raw_events_{run_id}.parquet"
    raw.to_parquet(staging_path, index=False)
    logger.info("Staged raw extract at %s", staging_path)

    artifacts = transform(raw)
    load_all(config, artifacts)

    result = PipelineResult(
        run_id=run_id,
        raw_row_count=len(raw),
        clean_row_count=len(artifacts["clean_events"]),
        quarantine_row_count=len(artifacts["quarantine"]),
        output_dir=str(config.output_dir),
    )
    logger.info(
        "Pipeline %s finished: %s raw, %s clean, %s quarantined",
        run_id,
        result.raw_row_count,
        result.clean_row_count,
        result.quarantine_row_count,
    )
    return result, artifacts
