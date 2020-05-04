import ipaddress
from contextlib import contextmanager
from contextvars import ContextVar
from types import SimpleNamespace
from typing import (  # noqa
    Any,
    Awaitable,
    Callable,
    Dict,
    Generator,
    List,
    Optional,
    Set,
    cast,
)

import aiohttp
from aiohttp.tracing import (
    TraceRequestEndParams,
    TraceRequestExceptionParams,
    TraceRequestStartParams,
)
from aiohttp.web import (
    Application,
    HTTPException,
    Request,
    Response,
    middleware,
)
from aiohttp.web_urldispatcher import AbstractRoute

from aiojaeger.constants import (
    HTTP_METHOD,
    HTTP_PATH,
    HTTP_ROUTE,
    HTTP_STATUS_CODE,
)
from aiojaeger.span import SpanAbc
from aiojaeger.spancontext import CLIENT, SERVER, BaseTraceContext
from aiojaeger.tracer import Tracer

APP_AIOJAEGER_KEY = "aiojaeger_tracer"
REQUEST_AIOJAEGER_KEY = "aiojaeger_span"

__all__ = (
    "APP_AIOJAEGER_KEY",
    "get_tracer",
    "jaeger_context",
    "make_trace_config",
    "middleware_maker",
    "REQUEST_AIOJAEGER_KEY",
    "request_span",
    "setup",
)

Handler = Callable[[Request], Awaitable[Response]]
Middleware = Callable[[Request, Handler], Awaitable[Response]]
OptTraceVar = ContextVar[Optional[BaseTraceContext]]

jaeger_context: OptTraceVar = ContextVar("jaeger_context", default=None)


def _set_remote_endpoint(span: SpanAbc, request: Request) -> None:
    peername = request.remote
    if peername is not None:
        kwargs: Dict[str, Any] = {}
        try:
            peer_ipaddress = ipaddress.ip_address(peername)
        except ValueError:
            pass
        else:
            if isinstance(peer_ipaddress, ipaddress.IPv4Address):
                kwargs["ipv4"] = str(peer_ipaddress)
            elif isinstance(peer_ipaddress, ipaddress.IPv6Address):
                kwargs["ipv6"] = str(peer_ipaddress)
            else:
                raise ValueError("Failed to parse address")

        if kwargs:
            span.remote_endpoint(None, **kwargs)


def _get_span(request: Request, tracer: Tracer) -> SpanAbc:
    return tracer.get_span(request.headers)


def _set_span_properties(span: SpanAbc, request: Request) -> None:
    span_name = "{0} {1}".format(request.method.upper(), request.path)
    span.name(span_name)
    span.kind(SERVER)
    span.tag(HTTP_PATH, request.path)
    span.tag(HTTP_METHOD, request.method.upper())

    resource = request.match_info.route.resource
    # available only in aiohttp >= 3.3.1
    if getattr(resource, "canonical", None) is not None:
        route = request.match_info.route.resource.canonical
        span.tag(HTTP_ROUTE, route)

    _set_remote_endpoint(span, request)


@contextmanager
def set_context_value(
    context_var: OptTraceVar, value: BaseTraceContext
) -> Generator[OptTraceVar, None, None]:
    token = context_var.set(value)
    try:
        yield context_var
    finally:
        context_var.reset(token)


def middleware_maker(
    skip_routes: Optional[List[AbstractRoute]] = None,
    tracer_key: str = APP_AIOJAEGER_KEY,
    request_key: str = REQUEST_AIOJAEGER_KEY,
    match_path: str = "/",
) -> Middleware:
    s = skip_routes
    skip_routes_set: Set[AbstractRoute] = set(s) if s else set()

    _middleware: Callable[[Middleware], Middleware] = middleware

    @_middleware
    async def aiojaeger_middleware(
        request: Request, handler: Handler
    ) -> Response:
        # route is in skip list, we do not track anything with tracing
        if request.match_info.route in skip_routes_set:
            resp = await handler(request)
            return resp

        # skip not matched route
        if not request.path.startswith(match_path):
            return await handler(request)

        tracer = request.app[tracer_key]
        span = _get_span(request, tracer)
        request[request_key] = span
        if span.is_noop:
            resp = await handler(request)
            return resp

        with set_context_value(jaeger_context, span.context):
            with span:
                _set_span_properties(span, request)
                try:
                    resp = await handler(request)
                except HTTPException as e:
                    span.tag(HTTP_STATUS_CODE, e.status)
                    raise
                span.tag(HTTP_STATUS_CODE, resp.status)

        return resp

    return aiojaeger_middleware


def setup(
    app: Application,
    tracer: Tracer,
    *,
    skip_routes: Optional[List[AbstractRoute]] = None,
    tracer_key: str = APP_AIOJAEGER_KEY,
    request_key: str = REQUEST_AIOJAEGER_KEY,
    match_path: str = "/",
) -> Application:
    """Sets required parameters in aiohttp applications for aiojaeger.

    Tracer added into application context and cleaned after application
    shutdown. You can provide custom tracer_key, if default name is not
    suitable.
    """
    app[tracer_key] = tracer
    m = middleware_maker(
        skip_routes=skip_routes,
        tracer_key=tracer_key,
        request_key=request_key,
        match_path=match_path,
    )
    app.middlewares.append(m)  # type: ignore

    # register cleanup signal to close transport connections
    async def close_aiojaeger(app: Application) -> None:
        await app[tracer_key].close()

    app.on_cleanup.append(close_aiojaeger)

    return app


def get_tracer(
    app: Application, tracer_key: str = APP_AIOJAEGER_KEY
) -> Tracer:
    """Returns tracer object from application context.

    By default tracer has APP_AIOJAEGER_KEY in aiohttp application context,
    you can provide own key, if for some reason default one is not suitable.
    """
    return cast(Tracer, app[tracer_key])


def request_span(
    request: Request, request_key: str = REQUEST_AIOJAEGER_KEY
) -> SpanAbc:
    """Returns span created by middleware from request context, you can use it
    as parent on next child span.
    """
    return cast(SpanAbc, request[request_key])


class JaegerClientSignals:
    """Class contains signal handler for aiohttp client. Handlers executed
    only if aiohttp session contains tracer context with span.
    """

    def __init__(self, tracer: Tracer) -> None:
        self._tracer = tracer

    def _get_span_context(
        self, trace_config_ctx: SimpleNamespace
    ) -> Optional[BaseTraceContext]:
        trace_request_ctx = trace_config_ctx.trace_request_ctx
        has_explicit_context = (
            isinstance(trace_request_ctx, dict)
            and "span_context" in trace_request_ctx
        )
        if has_explicit_context:
            r: BaseTraceContext = trace_request_ctx["span_context"]
            return r

        has_implicit_context = jaeger_context.get() is not None
        if has_implicit_context:
            return jaeger_context.get()

        return None

    async def on_request_start(
        self,
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: TraceRequestStartParams,
    ) -> None:
        span_context = self._get_span_context(context)
        if span_context is None:
            return

        p = params
        span = self._tracer.new_child(span_context)
        context._span = span
        span.start()
        span_name = "client {0} {1}".format(p.method.upper(), p.url.path)
        span.name(span_name)
        span.kind(CLIENT)

        ctx = context.trace_request_ctx
        propagate_headers = ctx is None or ctx.get("propagate_headers", True)
        if propagate_headers:
            span_headers = span.context.make_headers()
            p.headers.update(span_headers)

    async def on_request_end(
        self,
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: TraceRequestEndParams,
    ) -> None:
        span_context = self._get_span_context(context)
        if span_context is None:
            return

        span = context._span
        span.finish()
        delattr(context, "_span")

    async def on_request_exception(
        self,
        session: aiohttp.ClientSession,
        context: SimpleNamespace,
        params: TraceRequestExceptionParams,
    ) -> None:

        span_context = self._get_span_context(context)
        if span_context is None:
            return
        span = context._span
        span.finish(exception=params.exception)
        delattr(context, "_span")


def make_trace_config(tracer: Tracer) -> aiohttp.TraceConfig:
    """Creates aiohttp.TraceConfig with enabled aiojaeger instrumentation
    for aiohttp client.
    """
    tc = aiohttp.TraceConfig()
    jaeger = JaegerClientSignals(tracer)

    tc.on_request_start.append(jaeger.on_request_start)  # type: ignore
    tc.on_request_end.append(jaeger.on_request_end)  # type: ignore
    tc.on_request_exception.append(jaeger.on_request_exception)  # type: ignore
    return tc
