import json
from pathlib import Path

import pandas as pd
import pytest


@pytest.fixture
def sample_event() -> dict:
    return {
        "policy_id": "POL-1",
        "customer_id": "CUS-1",
        "event_type": "purchase",
        "event_timestamp": "2024-06-01T10:00:00.000Z",
        "policy_type": "{'type': 'auto', 'brand': 'LifeSecure'}",
        "premium_amount": 100.0,
        "coverage_amount": 5000.0,
        "age_of_insured": 40,
        "region": "North",
    }


@pytest.fixture
def sample_raw_df(sample_event) -> pd.DataFrame:
    renewal = {
        **sample_event,
        "policy_id": "POL-2",
        "customer_id": "CUS-2",
        "event_type": "renewal",
        "event_timestamp": "2024-06-02T12:00:00.000Z",
        "policy_type": "{'type': 'auto', 'brand': 'InsureCorp'}",
        "premium_amount": 200.0,
    }
    cancellation = {
        **sample_event,
        "policy_id": "POL-3",
        "customer_id": "CUS-3",
        "event_type": "cancellation",
        "event_timestamp": "2024-06-03T08:00:00.000Z",
    }
    return pd.DataFrame([sample_event, renewal, cancellation])


@pytest.fixture
def temp_jsonl_dir(tmp_path, sample_event) -> Path:
    bad = {**sample_event, "policy_id": None, "event_type": "purchase"}
    overflow = {
        **sample_event,
        "policy_id": "POL-BAD",
        "coverage_amount": -2147483649,
        "event_type": "claim",
    }
    path = tmp_path / "part-00000.json"
    lines = [sample_event, bad, overflow]
    path.write_text("\n".join(json.dumps(row) for row in lines) + "\n")
    return tmp_path
