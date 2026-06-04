import pandas as pd

from policy_etl.transform import (
    build_mart_renewals_daily,
    clean_events,
    derive_policy_status,
    transform,
)


def test_clean_events_quarantines_invalid_rows(sample_raw_df):
    raw = sample_raw_df.copy()
    raw.loc[len(raw)] = {
        "policy_id": None,
        "customer_id": "CUS-X",
        "event_type": "purchase",
        "event_timestamp": "2024-01-01T00:00:00Z",
        "policy_type": "{'type': 'auto', 'brand': 'X'}",
        "premium_amount": 1,
        "coverage_amount": 1,
        "age_of_insured": 1,
        "region": "East",
    }
    clean, quarantine = clean_events(raw)
    assert len(clean) == 3
    assert len(quarantine) == 1
    assert "missing_policy_id" in quarantine.iloc[0]["validation_issues"]


def test_clean_events_quarantines_overflow_coverage(sample_raw_df):
    raw = sample_raw_df.copy()
    raw.loc[len(raw)] = {
        **raw.iloc[0].to_dict(),
        "policy_id": "POL-OVER",
        "coverage_amount": -2147483649,
        "event_type": "claim",
    }
    clean, quarantine = clean_events(raw)
    assert len(quarantine) == 1
    assert "invalid_coverage_amount" in quarantine.iloc[0]["validation_issues"]


def test_derive_policy_status_active_and_inactive(sample_raw_df):
    artifacts = transform(sample_raw_df)
    status = artifacts["mart_policy_status"]
    by_policy = status.set_index("policy_id")["status"].to_dict()
    assert by_policy["POL-1"] == "active"
    assert by_policy["POL-2"] == "active"
    assert by_policy["POL-3"] == "inactive"


def test_build_mart_renewals_daily_median(sample_raw_df):
    artifacts = transform(sample_raw_df)
    mart = artifacts["mart_renewals_daily"]
    auto_row = mart[mart["product_type"] == "auto"].iloc[0]
    assert auto_row["renewal_count"] == 1
    assert auto_row["median_premium"] == 200.0


def test_transform_produces_expected_tables(sample_raw_df):
    artifacts = transform(sample_raw_df)
    assert set(artifacts["dimensions"]) == {
        "dim_customer",
        "dim_product",
        "dim_region",
        "dim_policy",
    }
    assert len(artifacts["fact_policy_events"]) == 3
    assert "event_sk" in artifacts["fact_policy_events"].columns
