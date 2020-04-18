import time
from typing import Any, Dict, List, NamedTuple, Optional

from aiojaeger.mypy_types import OptInt, OptStr, OptTs

Endpoint = NamedTuple(
    "Endpoint",
    [
        ("serviceName", OptStr),
        ("ipv4", OptStr),
        ("ipv6", OptStr),
        ("port", OptInt),
    ],
)


def create_endpoint(
    service_name: str,
    *,
    ipv4: OptStr = None,
    ipv6: OptStr = None,
    port: OptInt = None
) -> Endpoint:
    """Factory function to create Endpoint object.
    """
    return Endpoint(service_name, ipv4, ipv6, port)


def make_timestamp(ts: OptTs = None) -> int:
    """Create timestamp in microseconds, or convert available one
    from second. Useful when user supplies ts from time.time() call.
    """
    ts = ts if ts is not None else time.time()
    return int(ts * 1000 * 1000)  # microseconds


OptKeys = Optional[List[str]]


def filter_none(data: Dict[str, Any], keys: OptKeys = None) -> Dict[str, Any]:
    """Filter keys from dict with None values.

    Check occurs only on root level. If list of keys specified, filter
    works only for selected keys
    """

    def limited_filter(k: str, v: Any) -> bool:
        return k not in keys or v is not None  # type: ignore

    def full_filter(k: str, v: Any) -> bool:
        return v is not None

    f = limited_filter if keys is not None else full_filter
    return {k: v for k, v in data.items() if f(k, v)}
