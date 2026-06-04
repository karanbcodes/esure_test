"""Example analyst queries against the loaded warehouse."""

from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd


def run_example_queries(sqlite_path: Path) -> dict[str, pd.DataFrame]:
    conn = sqlite3.connect(sqlite_path)

    active_customers = pd.read_sql_query(
        """
        SELECT COUNT(DISTINCT customer_sk) AS active_customer_count
        FROM mart_policy_status
        WHERE status = 'active'
        """,
        conn,
    )

    renewals_2024_by_type = pd.read_sql_query(
        """
        SELECT
            COALESCE(product_type, 'unknown') AS policy_type,
            COUNT(*) AS renewal_count
        FROM fact_policy_events
        WHERE event_type = 'renewal'
          AND event_timestamp >= '2024-01-01'
          AND event_timestamp < '2025-01-01'
        GROUP BY product_type
        ORDER BY renewal_count DESC
        """,
        conn,
    )

    median_auto_renewal_by_day = pd.read_sql_query(
        """
        SELECT
            event_date,
            renewal_count,
            median_premium
        FROM mart_renewals_daily
        WHERE product_type = 'auto'
        ORDER BY event_date
        """,
        conn,
    )

    conn.close()
    return {
        "active_customers": active_customers,
        "renewals_2024_by_type": renewals_2024_by_type,
        "median_auto_renewal_by_day": median_auto_renewal_by_day,
    }
