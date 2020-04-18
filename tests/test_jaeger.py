import asyncio

import pytest
from yarl import URL

import aiozipkin as az


@pytest.mark.asyncio
async def test_basic(jaeger_server, jaeger_url, jaeger_api_url, client, loop):
    endpoint = az.create_endpoint("simple_service", ipv4="127.0.0.1", port=80)
    tracer = await az.create_jaeger(jaeger_url, endpoint)
    with tracer.new_trace(sampled=True) as span:
        span.name("jaeger_span")
        span.tag("span_type", "root")
        span.kind(az.CLIENT)
        span.annotate("SELECT * FROM")
        await asyncio.sleep(0.1)
        span.annotate("start end sql")

    # close forced sending data to server regardless of send interval
    await tracer.close()

    # convert to hex
    trace_id = "%0.2x" % int(span.context.trace_id)
    url = URL(jaeger_api_url) / "api" / "traces" / trace_id
    resp = await client.get(url, headers={"Content-Type": "application/json"})
    assert resp.status == 200
    data = await resp.json()
    assert data["data"][0]["traceID"] == trace_id
