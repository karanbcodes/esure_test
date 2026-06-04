"""Parse malformed source fields into structured values."""

from __future__ import annotations

import ast
import json
import re
from typing import Any


def parse_policy_type(raw: Any) -> tuple[str | None, str | None]:
    """
    Source stores policy_type as a Python-dict-like string, e.g.
    "{'type': 'auto', 'brand': 'LifeSecure'}" including None literals.
    """
    if raw is None or (isinstance(raw, float) and str(raw) == "nan"):
        return None, None
    if isinstance(raw, dict):
        return raw.get("type"), raw.get("brand")

    text = str(raw).strip()
    if not text:
        return None, None

    # Normalise Python None to JSON null before json.loads where possible.
    normalised = re.sub(r"\bNone\b", "null", text)
    normalised = normalised.replace("'", '"')

    try:
        parsed = json.loads(normalised)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (SyntaxError, ValueError):
            return None, None

    if not isinstance(parsed, dict):
        return None, None

    policy_type = parsed.get("type")
    brand = parsed.get("brand")
    if policy_type == "null":
        policy_type = None
    if brand == "null":
        brand = None
    return policy_type, brand
