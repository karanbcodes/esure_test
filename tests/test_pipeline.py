from pathlib import Path

import pytest

from policy_etl.analytics import run_example_queries
from policy_etl.config import PipelineConfig
from policy_etl.pipeline import run_pipeline


@pytest.fixture
def pipeline_config(tmp_path, temp_jsonl_dir) -> PipelineConfig:
    return PipelineConfig(
        input_dir=temp_jsonl_dir,
        output_dir=tmp_path / "output",
        run_id="test-run",
    )


def test_run_pipeline_end_to_end(pipeline_config):
    result, artifacts = run_pipeline(pipeline_config)
    assert result.raw_row_count == 3
    assert result.clean_row_count == 1
    assert result.quarantine_row_count == 2
    assert pipeline_config.sqlite_path.exists()
    assert (pipeline_config.warehouse_dir / "fact_policy_events.parquet").exists()
    assert len(artifacts["fact_policy_events"]) == 1


def test_example_queries_on_warehouse(pipeline_config):
    run_pipeline(pipeline_config)
    queries = run_example_queries(pipeline_config.sqlite_path)
    assert "active_customers" in queries
    assert queries["active_customers"].columns.tolist() == ["active_customer_count"]
