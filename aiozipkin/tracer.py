from typing import TYPE_CHECKING  # noqa
from typing import Any, AsyncContextManager, Awaitable, Dict, Optional

from aiozipkin.context_managers import _ContextManager

from .helpers import Endpoint
from .mypy_types import Headers, OptBool
from .record import Record
from .sampler import Sampler, SamplerABC
from .span import NoopSpan, Span, SpanAbc
from .spancontext import BaseTraceContext
from .transport import (
    StubTransport,
    ThriftTransport,
    TransportABC,
    ZipkinTransport,
)

if TYPE_CHECKING:

    class _Base(AsyncContextManager["Tracer"]):
        pass


else:

    class _Base(AsyncContextManager):
        pass


class Tracer(_Base):
    def __init__(
        self,
        transport: TransportABC,
        sampler: SamplerABC,
        local_endpoint: Endpoint,
    ) -> None:
        super().__init__()
        self._records: Dict[str, Record] = {}
        self._transport = transport
        self._sampler = sampler
        self._local_endpoint = local_endpoint

    def new_trace(
        self, sampled: OptBool = None, debug: bool = False
    ) -> SpanAbc:
        context = self._next_context(None, sampled=sampled, debug=debug)
        return self.to_span(context)

    def join_span(self, context: BaseTraceContext) -> SpanAbc:
        new_context = context
        if context.sampled is None:
            sampled = self._sampler.is_sampled(context.trace_id)
            new_context.sampled = sampled
        else:
            new_context.shared = True
        return self.to_span(new_context)

    def new_child(self, context: BaseTraceContext) -> SpanAbc:
        new_context = self._next_context(context)
        if not context.sampled:
            return NoopSpan(self, new_context)
        return self.to_span(new_context)

    def to_span(self, context: BaseTraceContext) -> SpanAbc:
        if not context.sampled:
            return NoopSpan(self, context)

        record = Record(context, self._local_endpoint)
        self._records[context.span_id] = record
        return Span(self, context, record)

    def _send(self, record: Record) -> None:
        self._records.pop(record.context.span_id, None)
        self._transport.send(record)

    def _next_context(
        self,
        context: Optional[BaseTraceContext] = None,
        sampled: OptBool = None,
        debug: bool = False,
    ) -> BaseTraceContext:
        span_id = self._transport.generate_span_id()
        if context is not None:
            new_context = context
            new_context.span_id = span_id
            new_context.parent_id = context.span_id
            new_context.shared = False
            return new_context

        trace_id = self._transport.generate_trace_id()
        if sampled is None:
            sampled = self._sampler.is_sampled(trace_id)

        new_context = self._transport.span_context(
            trace_id=trace_id,
            parent_id=None,
            span_id=span_id,
            sampled=sampled,
            debug=debug,
            shared=False,
        )
        return new_context

    async def close(self) -> None:
        await self._transport.close()

    async def __aenter__(self) -> "Tracer":
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    def make_context(self, headers: Headers):
        return self._transport.span_context.make_context(headers)


def create_zipkin(
    zipkin_address: str,
    local_endpoint: Endpoint,
    *,
    sample_rate: float = 0.01,
    send_interval: float = 5,
) -> Awaitable[Tracer]:
    async def build_tracer() -> Tracer:
        sampler = Sampler(sample_rate=sample_rate)
        transport = ZipkinTransport(
            zipkin_address, send_interval=send_interval
        )
        return Tracer(transport, sampler, local_endpoint)

    return _ContextManager(build_tracer())


def create_jaeger(
    jaeger_url: str,
    local_endpoint: Endpoint,
    *,
    sample_rate: float = 0.01,
    send_interval: float = 5,
) -> Awaitable[Tracer]:
    async def build_tracer() -> Tracer:
        transport = ThriftTransport(
            address=jaeger_url, send_interval=send_interval
        )
        sampler = Sampler(sample_rate=sample_rate)
        return Tracer(transport, sampler, local_endpoint)

    return _ContextManager(build_tracer())


def create_custom(
    local_endpoint: Endpoint,
    transport: Optional[TransportABC] = None,
    sampler: Optional[SamplerABC] = None,
) -> Awaitable[Tracer]:
    t = transport or StubTransport()
    sample_rate = 1  # sample everything
    s = sampler or Sampler(sample_rate=sample_rate)

    async def build_tracer() -> Tracer:
        return Tracer(t, s, local_endpoint)

    return _ContextManager(build_tracer())
