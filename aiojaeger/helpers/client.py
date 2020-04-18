import logging
from typing import List, Optional

from aiohttp import TraceConfig
from aiohttp.web import AbstractRoute, Application

import aiojaeger as aj

log = logging.getLogger(__name__)


class TracingClient:
    __slots__ = (
        "_address",
        "_endpoint",
        "trace_config",
        "_tracer",
        "_sample_rate",
    )

    def __init__(self, address: str, service_name: str, host: str, port: int,
                 sample_rate: float = 1.0):
        self._address = address
        self._endpoint = aj.create_endpoint(service_name, ipv6=host, port=port)
        self._tracer: Optional[aj.Tracer] = None
        self._sample_rate = sample_rate
        self.trace_config: Optional[TraceConfig] = None

    async def close(self) -> None:
        if self._tracer:
            await self._tracer.close()

    async def setup(self) -> None:
        self._tracer = await aj.create_jaeger(
            self._address, self._endpoint, sample_rate=self._sample_rate
        )
        self.trace_config = aj.make_trace_config(self._tracer)

    def middleware(
        self, app: Application, skip_routes: List[AbstractRoute]
    ) -> Application:
        if not self._tracer:
            log.warning("Failed to setup aiojaeger. Call setup method before")
            return app
        return aj.setup(app, self._tracer, skip_routes=skip_routes)

    @property
    def tracer(self) -> aj.Tracer:
        if not self._tracer:
            raise ValueError
        return self._tracer
