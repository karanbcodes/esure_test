"""Extract raw policy events from JSON Lines files."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def discover_input_files(input_dir: Path) -> list[Path]:
    files = sorted(input_dir.glob("*.json"))
    if not files:
        raise FileNotFoundError(f"No JSON files found in {input_dir}")
    return files


def read_json_lines(path: Path) -> list[dict]:
    records: list[dict] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSON in %s line %s: %s", path.name, line_no, exc)
    return records


def extract_raw_events(input_dir: Path) -> pd.DataFrame:
    """Read all JSONL part files into a single raw dataframe."""
    frames: list[pd.DataFrame] = []
    for path in discover_input_files(input_dir):
        records = read_json_lines(path)
        if not records:
            continue
        frame = pd.DataFrame(records)
        frame["_source_file"] = path.name
        frames.append(frame)

    if not frames:
        raise ValueError(f"No records extracted from {input_dir}")

    combined = pd.concat(frames, ignore_index=True)
    combined["_extracted_at"] = pd.Timestamp.utcnow().isoformat()
    logger.info("Extracted %s events from %s files", len(combined), len(frames))
    return combined
