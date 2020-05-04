from aiojaeger.helpers import Endpoint
from aiojaeger.record import Record
from aiojaeger.spancontext import DummyTraceContext


def test_basic_ctr():
    context = DummyTraceContext(
        trace_id=1,
        span_id=2,
        parent_id=3,
        sampled=True,
        debug=True,
        shared=True,
    )
    local_endpoint = Endpoint("string", "string", "string", 0)
    remote_endpoint = Endpoint("string", "string", "string", 0)
    record = (
        Record(context, local_endpoint)
        .start(0)
        .name("string")
        .set_tag("additionalProp1", "string")
        .set_tag("additionalProp2", "string")
        .set_tag("additionalProp3", "string")
        .kind("CLIENT")
        .annotate("string", 0)
        .remote_endpoint(remote_endpoint)
        .finish(0)
    )
    dict_record = record.asdict()
    expected = {
        "traceId": "01",
        "name": "string",
        "parentId": "03",
        "id": "02",
        "kind": "CLIENT",
        "timestamp": 0,
        "duration": 1,
        "debug": True,
        "shared": True,
        "localEndpoint": {
            "serviceName": "string",
            "ipv4": "string",
            "ipv6": "string",
            "port": 0,
        },
        "remoteEndpoint": {
            "serviceName": "string",
            "ipv4": "string",
            "ipv6": "string",
            "port": 0,
        },
        "annotations": [{"timestamp": 0, "value": "string"}],
        "tags": {
            "additionalProp1": "string",
            "additionalProp2": "string",
            "additionalProp3": "string",
        },
    }
    assert dict_record == expected
