import abc
import asyncio
import logging
import os
from collections import deque
from typing import (  # flake8: noqa
    Any,
    Awaitable,
    Callable,
    Deque,
    List,
    Optional,
    Tuple,
    Type,
    Union,
)

import aiohttp
import thriftpy2
from aiohttp import hdrs
from aiohttp.client_exceptions import ClientError, ClientResponseError
from thriftpy2.protocol import TBinaryProtocolFactory

from .record import Record
from .spancontext import BaseTraceContext, DummyTraceContext
from .spancontext.jaeger import JaegerTraceContext
from .spancontext.zipkin import ZipkinTraceContext
from .utils import (generate_random_128bit_string,
                    generate_random_64bit_string, random_id)

try:
    from thriftpy2.transport import TCyMemoryBuffer as TMemoryBuffer
except ImportError:
    from thriftpy2.transport import TMemoryBuffer
import aiojaeger

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = aiohttp.ClientTimeout(total=5 * 60)
BATCHES_MAX_COUNT = 10 ** 4

DataList = List[Record]
SndBatches = Deque[Tuple[int, DataList]]
SendDataCoro = Callable[[DataList], Awaitable[bool]]


class TransportABC(abc.ABC):
    @abc.abstractmethod
    def send(self, record: Record) -> None:  # pragma: no cover
        """Sends data to abstract collector."""
        pass

    @abc.abstractmethod
    async def close(self) -> None:  # pragma: no cover
        """Performs additional cleanup actions if required."""
        pass

    @abc.abstractmethod
    def generate_trace_id(self) -> Union[int, str]:
        pass

    @abc.abstractmethod
    def generate_span_id(self) -> Union[int, str]:
        pass

    @property
    @abc.abstractmethod
    def span_context(self) -> Type[BaseTraceContext]:
        pass

    def endpoint(self, local_endpoint):
        pass


class StubTransport(TransportABC):
    """Dummy transport, which logs spans to a limited queue."""

    def __init__(self, queue_length: int = 100) -> None:
        logger.info("Collector address was not provided, using stub transport")
        self.records: Deque[Record] = deque(maxlen=queue_length)

    def send(self, record: Record) -> None:
        self.records.append(record)

    async def close(self) -> None:
        pass

    def gen(self) -> str: return ""

    generate_trace_id = gen
    generate_span_id = gen

    @property
    def span_context(self) -> Type[BaseTraceContext]:
        return DummyTraceContext


class StubZipkinTransport(StubTransport):
    @property
    def span_context(self) -> Type[BaseTraceContext]:
        return ZipkinTraceContext


class StubJaegerTransport(StubTransport):
    @property
    def span_context(self) -> Type[BaseTraceContext]:
        return JaegerTraceContext


class BatchManager:
    def __init__(
        self,
        max_size: int,
        send_interval: float,
        attempt_count: int,
        send_data: SendDataCoro,
    ) -> None:
        loop = asyncio.get_event_loop()
        self._max_size = max_size
        self._send_interval = send_interval
        self._send_data = send_data
        self._attempt_count = attempt_count
        self._max = BATCHES_MAX_COUNT
        self._sending_batches: SndBatches = deque([], maxlen=self._max)
        self._active_batch: Optional[DataList] = None
        self._ender = loop.create_future()
        self._timer: Optional[asyncio.Future[Any]] = None
        self._sender_task = asyncio.ensure_future(self._sender_loop())

    def add(self, data: Any) -> None:
        if self._active_batch is None:
            self._active_batch = []
        self._active_batch.append(data)
        if len(self._active_batch) >= self._max_size:
            self._sending_batches.append((0, self._active_batch))
            self._active_batch = None
            if self._timer is not None and not self._timer.done():
                self._timer.cancel()

    async def stop(self) -> None:
        if self._ender.done():
            return None

        self._ender.set_result(None)

        await self._sender_task
        await self._send()

        if self._timer is not None:
            self._timer.cancel()
            try:
                await self._timer
            except asyncio.CancelledError:
                pass

    async def _sender_loop(self) -> None:
        while not self._ender.done():
            await self._wait()
            await self._send()

    async def _send(self) -> None:
        if self._active_batch is not None:
            self._sending_batches.append((0, self._active_batch))
            self._active_batch = None

        batches = self._sending_batches.copy()
        self._sending_batches = deque([], maxlen=self._max)
        for attempt, batch in batches:
            if not await self._send_data(batch):
                attempt += 1
                if attempt < self._attempt_count:
                    self._sending_batches.append((attempt, batch))

    async def _wait(self) -> None:
        self._timer = asyncio.ensure_future(asyncio.sleep(self._send_interval))

        await asyncio.wait(
            [self._timer, self._ender], return_when=asyncio.FIRST_COMPLETED,
        )


class ZipkinTransport(TransportABC):
    def __init__(
        self,
        address: str,
        send_interval: float = 5,
        *,
        send_max_size: int = 100,
        send_attempt_count: int = 3,
        send_timeout: Optional[aiohttp.ClientTimeout] = None
    ) -> None:
        self._queue: DataList = []
        self._closing = False
        self._address = address
        self._send_interval = send_interval

        if send_timeout is None:
            send_timeout = DEFAULT_TIMEOUT

        self._session = aiohttp.ClientSession(
            timeout=send_timeout, headers={"Content-Type": "application/json"}
        )
        self._batch_manager = BatchManager(
            send_max_size, send_interval, send_attempt_count, self._send_data
        )

    def send(self, record: Record) -> None:
        self._batch_manager.add(record)

    async def _send_data(self, records: List[Record]) -> bool:
        data = [record.asdict() for record in records]
        try:
            async with self._session.post(self._address, json=data) as resp:
                body = await resp.text()
                if resp.status >= 300:
                    msg = "zipkin responded with code: {} and body: {}".format(
                        resp.status, body
                    )
                    raise RuntimeError(msg)

        except (asyncio.TimeoutError, ClientError):
            return False
        except Exception as exc:  # pylint: disable=broad-except
            # that code should never fail and break application
            logger.error("Can not send spans to zipkin", exc_info=exc)
        return True

    async def close(self) -> None:
        if self._closing:
            return

        self._closing = True
        await self._batch_manager.stop()
        await self._session.close()

    def generate_trace_id(self) -> Union[int, str]:
        return generate_random_128bit_string()

    def generate_span_id(self) -> Union[int, str]:
        return generate_random_64bit_string()

    @property
    def span_context(self) -> Type[BaseTraceContext]:
        return ZipkinTraceContext


class ThriftTransport(TransportABC):
    MODULE_PATH = os.path.abspath(os.path.dirname(aiojaeger.__file__))
    jaeger_thrift = thriftpy2.load(
        os.path.join(MODULE_PATH, "jaeger-idl/thrift/jaeger.thrift"),
        module_name="jaeger_thrift",
    )

    def __init__(
        self,
        address: str,
        send_interval: float = 5,
        *,
        send_max_size: int = 100,
        send_attempt_count: int = 3,
        send_timeout: Optional[aiohttp.ClientTimeout] = None
    ) -> None:

        if send_timeout is None:
            send_timeout = DEFAULT_TIMEOUT

        self._address = address
        self._batch_manager = BatchManager(
            send_max_size, send_interval, send_attempt_count, self._send_data
        )
        self._session = aiohttp.ClientSession(
            timeout=send_timeout,
            headers={hdrs.CONTENT_TYPE: "application/x-thrift"},
        )
        self._binary = TBinaryProtocolFactory(strict_read=False)

    async def close(self) -> None:
        self._closing = True
        await self._batch_manager.stop()

    def send(self, record: Record) -> None:
        self._batch_manager.add(record)

    async def _send_data(self, data: List[Record]) -> bool:
        if not data:
            return True
        batch = self.jaeger_thrift.Batch()
        process = self.jaeger_thrift.Process()
        process.serviceName = data[0].entrypoint_servicename

        batch.process = process
        spans = []
        for record in data:
            span = self.jaeger_thrift.Span()
            span.traceIdLow = int(record.context.trace_id)
            span.traceIdHigh = 0
            span.spanId = int(record.context.span_id)
            span.parentSpanId = int(
                record.context.parent_id if record.context.parent_id else 0
            )
            span.operationName = record._name
            span.startTime = record._timestamp
            span.duration = record._duration
            span.flags = 0
            if record._kind:
                tag = self.jaeger_thrift.Tag()
                tag.key = "span.kind"
                tag.vType = self.jaeger_thrift.TagType.STRING
                tag.vStr = record._kind
                span.tags = [tag]
            spans.append(span)
        batch.spans = spans

        otrans = TMemoryBuffer()
        self._binary.get_protocol(otrans).write_struct(batch)
        try:
            await self._session.post(self._address, data=otrans.getvalue())
        except ClientResponseError:
            logger.exception("Can not send spans to jaeger")
            return False
        return True

    def generate_trace_id(self) -> int:
        # TODO: support 128 bit header
        return random_id()

    def generate_span_id(self) -> int:
        return random_id()

    @property
    def span_context(self) -> Type[BaseTraceContext]:
        return JaegerTraceContext
