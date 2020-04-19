import pytest

from aiojaeger.spancontext.jaeger import JaegerConst


@pytest.mark.parametrize(
    "trace_id",
    [
        123.321,
        "1:1:1:1:1",
        "1:1:1",
        "x:1:1:1",
        "1:x:1:1",
        "1:1:x:1",
        "1:1:1:x",
        "0:1:1:1",
        "1:0:1:1",
        "1:1:-1:1",
        "1:1::1",
        "1:1:1:-1",
    ],
)
def tests_trace_context_from_bad_string(trace_id):
    with pytest.raises(ValueError):
        JaegerConst.parse_trace_id(trace_id)
