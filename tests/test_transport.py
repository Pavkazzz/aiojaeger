import asyncio

import pytest
from aiohttp.client import ClientTimeout
from async_timeout import timeout

import aiojaeger as az
import aiojaeger.transport as azt
from aiojaeger.utils import hexify


@pytest.mark.asyncio
async def test_retry(fake_zipkin, loop):
    endpoint = az.create_endpoint("simple_service", ipv4="127.0.0.1", port=80)

    tr = azt.ZipkinTransport(
        fake_zipkin.url,
        send_interval=0.01,
        send_max_size=100,
        send_attempt_count=3,
        send_timeout=ClientTimeout(total=1),
    )
    fake_zipkin.next_errors.append("disconnect")
    fake_zipkin.next_errors.append("timeout")
    waiter = fake_zipkin.wait_data(1)
    tracer = await az.create_custom(endpoint, tr)

    with tracer.new_trace(sampled=True) as span:
        span.name("root_span")
        span.kind(az.CLIENT)

    async with timeout(10):
        await waiter
    await tracer.close()

    data = fake_zipkin.get_received_data()
    trace_id = hexify(span.context.trace_id)
    assert any(s["traceId"] == trace_id for trace in data for s in trace), data


@pytest.mark.asyncio
async def test_batches(fake_zipkin, loop):
    endpoint = az.create_endpoint("simple_service", ipv4="127.0.0.1", port=80)

    tr = azt.ZipkinTransport(
        fake_zipkin.url,
        send_interval=0.01,
        send_max_size=2,
        send_timeout=ClientTimeout(total=1),
    )

    tracer = await az.create_custom(endpoint, tr)

    with tracer.new_trace(sampled=True) as span:
        span.name("root_span")
        span.kind(az.CLIENT)
        with span.new_child("child_1", az.CLIENT):
            pass
        with span.new_child("child_2", az.CLIENT):
            pass

    # close forced sending data to server regardless of send interval
    await tracer.close()

    data = fake_zipkin.get_received_data()
    trace_id = hexify(span.context.trace_id)
    assert len(data[0]) == 2
    assert len(data[1]) == 1
    assert data[0][0]["name"] == "child_1"
    assert data[0][1]["name"] == "child_2"
    assert data[1][0]["name"] == "root_span"
    assert any(s["traceId"] == trace_id for trace in data for s in trace), data


@pytest.mark.asyncio
async def test_send_full_batch(fake_zipkin, loop):
    endpoint = az.create_endpoint("simple_service", ipv4="127.0.0.1", port=80)

    tr = azt.ZipkinTransport(
        fake_zipkin.url,
        send_interval=60,
        send_max_size=2,
        send_timeout=ClientTimeout(total=1),
    )

    tracer = await az.create_custom(endpoint, tr)
    waiter = fake_zipkin.wait_data(1)

    with tracer.new_trace(sampled=True) as span:
        span.name("root_span")
        span.kind(az.CLIENT)

    await asyncio.sleep(1)

    data = fake_zipkin.get_received_data()
    assert len(data) == 0

    with tracer.new_trace(sampled=True) as span:
        span.name("root_span")
        span.kind(az.CLIENT)

    # batch is full here
    async with timeout(1):
        await waiter
    data = fake_zipkin.get_received_data()
    assert len(data) == 1

    # close forced sending data to server regardless of send interval
    await tracer.close()


@pytest.mark.asyncio
async def test_lost_spans(fake_zipkin, loop):
    endpoint = az.create_endpoint("simple_service", ipv4="127.0.0.1", port=80)

    tr = azt.ZipkinTransport(
        fake_zipkin.url,
        send_interval=0.01,
        send_max_size=100,
        send_attempt_count=2,
        send_timeout=ClientTimeout(total=1),
    )

    fake_zipkin.next_errors.append("disconnect")
    fake_zipkin.next_errors.append("disconnect")

    tracer = await az.create_custom(endpoint, tr)

    with tracer.new_trace(sampled=True) as span:
        span.name("root_span")
        span.kind(az.CLIENT)

    await asyncio.sleep(1)

    await tracer.close()

    data = fake_zipkin.get_received_data()
    assert len(data) == 0
