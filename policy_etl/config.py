from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# Sentinel values observed in source data (32-bit int overflow artefact).
INVALID_COVERAGE_THRESHOLD = -1_000_000_000

VALID_EVENT_TYPES = frozenset({"purchase", "renewal", "cancellation", "claim"})
ACTIVE_STATUS_EVENTS = frozenset({"purchase", "renewal"})
INACTIVE_STATUS_EVENTS = frozenset({"cancellation"})


@dataclass(frozen=True)
class PipelineConfig:
    input_dir: Path
    output_dir: Path
    run_id: str | None = None

    @property
    def staging_dir(self) -> Path:
        return self.output_dir / "staging"

    @property
    def warehouse_dir(self) -> Path:
        return self.output_dir / "warehouse"

    @property
    def quarantine_dir(self) -> Path:
        return self.output_dir / "quarantine"

    @property
    def sqlite_path(self) -> Path:
        return self.warehouse_dir / "policy_analytics.db"
