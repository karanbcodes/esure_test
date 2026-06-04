"""Transform raw events into a normalized analytical data model."""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from policy_etl.config import (
    ACTIVE_STATUS_EVENTS,
    INACTIVE_STATUS_EVENTS,
    INVALID_COVERAGE_THRESHOLD,
    VALID_EVENT_TYPES,
)
from policy_etl.parsers import parse_policy_type

logger = logging.getLogger(__name__)

REQUIRED_COLUMNS = frozenset(
    {"policy_id", "customer_id", "event_type", "event_timestamp"}
)


def _validate_row(row: pd.Series) -> list[str]:
    issues: list[str] = []
    for column in REQUIRED_COLUMNS:
        if pd.isna(row.get(column)) or row.get(column) == "":
            issues.append(f"missing_{column}")

    event_type = row.get("event_type")
    if pd.notna(event_type) and str(event_type) not in VALID_EVENT_TYPES:
        issues.append("invalid_event_type")

    coverage = row.get("coverage_amount")
    if pd.notna(coverage) and float(coverage) <= INVALID_COVERAGE_THRESHOLD:
        issues.append("invalid_coverage_amount")

    return issues


def clean_events(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Apply typing, parsing, and validation.
    Returns (clean_events, quarantined_events).
    """
    working = raw.copy()
    working["event_timestamp"] = pd.to_datetime(
        working["event_timestamp"], utc=True, errors="coerce"
    )
    working["premium_amount"] = pd.to_numeric(working["premium_amount"], errors="coerce")
    working["coverage_amount"] = pd.to_numeric(working["coverage_amount"], errors="coerce")
    working["age_of_insured"] = pd.to_numeric(working["age_of_insured"], errors="coerce")

    parsed = working["policy_type"].apply(parse_policy_type)
    working["product_type"] = parsed.apply(lambda x: x[0])
    working["brand"] = parsed.apply(lambda x: x[1])

    working["validation_issues"] = working.apply(_validate_row, axis=1)
    working["is_valid"] = working["validation_issues"].apply(len) == 0

    invalid_ts = working["event_timestamp"].isna()
    if invalid_ts.any():
        working.loc[invalid_ts, "validation_issues"] = working.loc[
            invalid_ts, "validation_issues"
        ].apply(lambda issues: issues + ["invalid_event_timestamp"])
        working.loc[invalid_ts, "is_valid"] = False

    quarantine = working[~working["is_valid"]].copy()
    clean = working[working["is_valid"]].copy()
    logger.info(
        "Validation complete: %s clean, %s quarantined",
        len(clean),
        len(quarantine),
    )
    return clean, quarantine


def build_dimensions(clean: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Build conformed dimension tables (type-1 slowly changing)."""
    customers = (
        clean[["customer_id"]]
        .drop_duplicates()
        .sort_values("customer_id")
        .reset_index(drop=True)
    )
    customers["customer_sk"] = range(1, len(customers) + 1)

    products = (
        clean[["product_type", "brand"]]
        .drop_duplicates()
        .sort_values(["product_type", "brand"], na_position="last")
        .reset_index(drop=True)
    )
    products["product_sk"] = range(1, len(products) + 1)

    regions = (
        clean[["region"]]
        .dropna()
        .drop_duplicates()
        .sort_values("region")
        .reset_index(drop=True)
    )
    regions["region_sk"] = range(1, len(regions) + 1)

    policies = (
        clean.groupby("policy_id", as_index=False)
        .agg(
            customer_id=("customer_id", "first"),
            product_type=("product_type", "first"),
            brand=("brand", "first"),
            region=("region", "first"),
        )
        .sort_values("policy_id")
        .reset_index(drop=True)
    )
    policies["policy_sk"] = range(1, len(policies) + 1)

    return {
        "dim_customer": customers,
        "dim_product": products,
        "dim_region": regions,
        "dim_policy": policies,
    }


def build_fact_policy_events(
    clean: pd.DataFrame, dimensions: dict[str, pd.DataFrame]
) -> pd.DataFrame:
    """Fact table at event grain with surrogate keys."""
    dim_policy = dimensions["dim_policy"]
    dim_customer = dimensions["dim_customer"]
    dim_product = dimensions["dim_product"]
    dim_region = dimensions["dim_region"]

    fact = clean.merge(
        dim_policy[["policy_id", "policy_sk", "customer_id"]],
        on="policy_id",
        how="left",
        suffixes=("", "_dim"),
    )
    fact = fact.merge(dim_customer, on="customer_id", how="left")
    fact = fact.merge(
        dim_product,
        on=["product_type", "brand"],
        how="left",
    )
    fact = fact.merge(dim_region, on="region", how="left", suffixes=("", "_region"))

    fact["event_date"] = fact["event_timestamp"].dt.date
    fact["event_sk"] = range(1, len(fact) + 1)

    columns = [
        "event_sk",
        "policy_sk",
        "customer_sk",
        "product_sk",
        "region_sk",
        "policy_id",
        "customer_id",
        "event_type",
        "event_timestamp",
        "event_date",
        "product_type",
        "brand",
        "region",
        "premium_amount",
        "coverage_amount",
        "age_of_insured",
    ]
    if "_source_file" in fact.columns:
        columns.append("_source_file")
    return fact[columns].sort_values("event_timestamp").reset_index(drop=True)


def derive_policy_status(fact: pd.DataFrame) -> pd.DataFrame:
    """
    Current policy status from latest event per policy.
    Active if latest lifecycle event is purchase or renewal.
    """
    lifecycle = fact[fact["event_type"].isin(ACTIVE_STATUS_EVENTS | INACTIVE_STATUS_EVENTS)]
    if lifecycle.empty:
        return pd.DataFrame(
            columns=["policy_sk", "policy_id", "customer_sk", "status", "last_event_at"]
        )

    latest = (
        lifecycle.sort_values("event_timestamp")
        .groupby("policy_sk", as_index=False)
        .tail(1)
    )
    latest["status"] = latest["event_type"].apply(
        lambda et: "active" if et in ACTIVE_STATUS_EVENTS else "inactive"
    )
    return latest[
        ["policy_sk", "policy_id", "customer_sk", "status", "event_timestamp", "event_type"]
    ].rename(columns={"event_timestamp": "last_event_at", "event_type": "last_event_type"})


def build_mart_renewals_daily(fact: pd.DataFrame) -> pd.DataFrame:
    """Pre-aggregate renewals for median premium by product type and day."""
    renewals = fact[fact["event_type"] == "renewal"].copy()
    if renewals.empty:
        return pd.DataFrame(
            columns=["event_date", "product_type", "renewal_count", "median_premium"]
        )

    grouped = (
        renewals.groupby(["event_date", "product_type"], dropna=False)
        .agg(
            renewal_count=("event_sk", "count"),
            median_premium=("premium_amount", "median"),
        )
        .reset_index()
    )
    return grouped.sort_values(["event_date", "product_type"])


def transform(raw: pd.DataFrame) -> dict[str, Any]:
    """Full transform: clean, dimensions, facts, and marts."""
    clean, quarantine = clean_events(raw)
    dimensions = build_dimensions(clean)
    fact = build_fact_policy_events(clean, dimensions)
    policy_status = derive_policy_status(fact)
    mart_renewals = build_mart_renewals_daily(fact)

    return {
        "clean_events": clean,
        "quarantine": quarantine,
        "dimensions": dimensions,
        "fact_policy_events": fact,
        "mart_policy_status": policy_status,
        "mart_renewals_daily": mart_renewals,
    }
