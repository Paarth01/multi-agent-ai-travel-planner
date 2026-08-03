"""
Builds deterministic cache keys from a prefix and arbitrary parameters.
Same params (regardless of dict insertion order) always produce the
same key, so e.g. search_flights(origin="Delhi", destination="Mumbai")
and search_flights(destination="Mumbai", origin="Delhi") hit the same
cache entry.
"""
import hashlib
import json


def build_key(prefix: str, **params) -> str:
    normalized = json.dumps(params, sort_keys=True, default=str)
    digest = hashlib.sha256(normalized.encode()).hexdigest()[:16]
    return f"{prefix}:{digest}"
