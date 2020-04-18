from contextlib import contextmanager
from typing import TYPE_CHECKING, Any, Callable, Dict, Generator, Optional

from aiojaeger import PRODUCER
from aiojaeger.helpers.aiohttp import jaeger_context
from aiojaeger.helpers.client import TracingClient
from aiojaeger.mypy_types import Headers
from aiojaeger.span import SpanAbc

if TYPE_CHECKING:

    class Message:
        @property
        def headers(self) -> Headers:
            pass

    class AbstractMaster:
        async def create_task(
            self,
            channel_name: str,
            kwargs: Optional[Dict[Any, Any]],
            *,
            headers: Headers,
            **message_kwargs: Any,
        ) -> None:
            pass

        async def on_message(
            self, func: Callable[[Any], Any], message: Message
        ) -> None:
            pass


else:

    class AbstractMaster:
        pass


class TracingAioPikaMaster(AbstractMaster):
    def __init__(self, tracing: TracingClient) -> None:
        self._tracing = tracing

    @contextmanager
    def _producer(
        self, channel: str, headers: Headers
    ) -> Generator[Headers, None, None]:
        context = jaeger_context.get()
        if not context:
            yield headers
            return

        span: SpanAbc = self._tracing.tracer.new_child(context)
        span.name(f"AMQP send to channel {channel}").kind(PRODUCER)
        headers = self._tracing.tracer.make_headers(context)
        with span:
            yield headers

    @contextmanager
    def _consumer(self, message: Message) -> Generator[None, None, None]:
        context = jaeger_context.get()
        if not context:
            yield
            return

        span = self._tracing.tracer.get_span(message.headers)
        with span:
            yield

    async def create_task(
        self,
        channel_name: str,
        kwargs: Dict[Any, Any] = None,
        **message_kwargs: Headers,
    ) -> None:
        headers: Headers = message_kwargs.pop("headers", {})
        with self._producer(channel_name, headers) as msg_headers:
            return await super().create_task(
                channel_name, kwargs, headers=msg_headers, **message_kwargs
            )

    async def on_message(
        self, func: Callable[[Any], Any], message: Message
    ) -> None:
        with self._consumer(message):
            return await super().on_message(func, message)
