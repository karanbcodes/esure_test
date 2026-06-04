#!/usr/bin/env python3
"""CLI entry point for the policy events ETL pipeline."""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from policy_etl.analytics import run_example_queries
from policy_etl.config import PipelineConfig
from policy_etl.pipeline import run_pipeline

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    root = Path(__file__).resolve().parent
    parser = argparse.ArgumentParser(
        description="ETL pipeline for policy event JSON data.",
    )
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=root / "policy_data",
        help="Directory containing JSON Lines part files",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=root / "output",
        help="Directory for warehouse outputs (Parquet + SQLite)",
    )
    parser.add_argument(
        "--run-queries",
        action="store_true",
        help="Run example analyst queries after load",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = PipelineConfig(input_dir=args.input_dir, output_dir=args.output_dir)

    if not config.input_dir.is_dir():
        logger.error("Input directory does not exist: %s", config.input_dir)
        return 1

    result, _ = run_pipeline(config)
    print(f"Pipeline run {result.run_id} completed successfully.")
    print(f"  Raw events:       {result.raw_row_count}")
    print(f"  Clean events:     {result.clean_row_count}")
    print(f"  Quarantined:      {result.quarantine_row_count}")
    print(f"  Output directory: {result.output_dir}")

    if args.run_queries:
        queries = run_example_queries(config.sqlite_path)
        print("\n--- Example analyst queries ---\n")
        for name, frame in queries.items():
            print(f"## {name}")
            print(frame.to_string(index=False))
            print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
