from typing import Optional

import aiojaeger as aj


class TracingClient:
    __slots__ = (
        "_address",
        "_endpoint",
        "trace_config",
        "_tracer",
        "_sample_rate",
    )

    def __init__(self, address, service_name, host, port, sample_rate=1.0):
        self._address = address
        self._endpoint = aj.create_endpoint(service_name, ipv6=host, port=port)
        self._tracer: Optional[aj.Tracer] = None
        self._sample_rate = sample_rate
        self.trace_config = None

    async def close(self):
        if self._tracer:
            await self._tracer.close()

    async def setup(self):
        self._tracer = await aj.create_jaeger(
            self._address, self._endpoint, sample_rate=self._sample_rate
        )
        self.trace_config = aj.make_trace_config(self._tracer)

    def middleware(self, app, skip_routes):
        return aj.setup(app, self._tracer, skip_routes=skip_routes)

    @property
    def tracer(self):
        return self._tracer
