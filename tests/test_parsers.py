import pytest

from policy_etl.parsers import parse_policy_type


@pytest.mark.parametrize(
    "raw,expected_type,expected_brand",
    [
        ("{'type': 'auto', 'brand': 'LifeSecure'}", "auto", "LifeSecure"),
        ("{'type': None, 'brand': 'InsureCorp'}", None, "InsureCorp"),
        ({"type": "health", "brand": "SafeGuard"}, "health", "SafeGuard"),
        ("", None, None),
        (None, None, None),
        ("not-a-dict", None, None),
    ],
)
def test_parse_policy_type(raw, expected_type, expected_brand):
    assert parse_policy_type(raw) == (expected_type, expected_brand)
