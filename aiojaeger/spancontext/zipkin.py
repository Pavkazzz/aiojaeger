import logging
from typing import List, Optional

from aiojaeger.mypy_types import Headers, OptBool
from aiojaeger.spancontext import BaseTraceContext
from aiojaeger.utils import hexify

log = logging.getLogger(__name__)


class ZipkinConst:
    # zipkin headers, for more information see:
    # https://github.com/openzipkin/b3-propagation

    TRACE_ID_HEADER = "X-B3-TraceId"
    SPAN_ID_HEADER = "X-B3-SpanId"
    PARENT_ID_HEADER = "X-B3-ParentSpanId"
    FLAGS_HEADER = "X-B3-Flags"
    SAMPLED_ID_HEADER = "X-B3-Sampled"
    SINGLE_HEADER = "b3"
    DELIMITER = "-"
    DEBUG_MARKER = "d"

    @classmethod
    def make_headers(cls, context: BaseTraceContext) -> Headers:
        """Creates dict with zipkin headers from supplied trace context.
        """

        # TODO: toggle for make single header or remove single
        headers = {
            cls.TRACE_ID_HEADER: hexify(context.trace_id),
            cls.SPAN_ID_HEADER: hexify(context.span_id),
            cls.FLAGS_HEADER: "0",
            cls.SAMPLED_ID_HEADER: "1" if context.sampled else "0",
        }
        if context.parent_id > 0:
            headers[cls.PARENT_ID_HEADER] = hexify(context.parent_id)
        return headers

    @classmethod
    def make_single_header(cls, context: BaseTraceContext) -> Headers:
        """Creates dict with zipkin single header format.
        """
        # b3={TraceId}-{SpanId}-{SamplingState}-{ParentSpanId}
        c = context

        # encode sampled flag
        if c.debug:
            sampled = "d"
        elif c.sampled:
            sampled = "1"
        else:
            sampled = "0"

        params: List[str] = [hexify(c.trace_id), hexify(c.span_id), sampled]
        if c.parent_id > 0:
            params.append(hexify(c.parent_id))

        h = cls.DELIMITER.join(params)
        headers = {cls.SINGLE_HEADER: h}
        return headers

    @classmethod
    def parse_sampled_header(cls, headers: Headers) -> Optional[bool]:
        sampled = headers.get(cls.SAMPLED_ID_HEADER.lower(), None)
        if not bool(sampled):
            return None
        return sampled == "1"

    @classmethod
    def parse_debug_header(cls, headers: Headers) -> bool:
        return headers.get(cls.FLAGS_HEADER, "0") == "1"

    @classmethod
    def _parse_parent_id(cls, parts: List[str]) -> int:
        # parse parent_id part from zipkin single header propagation
        parent_id = None
        if len(parts) >= 4:
            parent_id = parts[3]

        if not parent_id:
            return 0

        try:
            return int(parent_id, 16)
        except TypeError:
            log.warning("Fail to parse parent_id: %r", parent_id)
            return 0

    @classmethod
    def _parse_debug(cls, parts: List[str]) -> bool:
        # parse debug part from zipkin single header propagation
        debug = False
        if len(parts) >= 3 and parts[2] == cls.DEBUG_MARKER:
            debug = True
        return debug

    @classmethod
    def _parse_sampled(cls, parts: List[str]) -> OptBool:
        # parse sampled part from zipkin single header propagation
        sampled: OptBool = None
        if len(parts) >= 3:
            if parts[2] in ("1", "0"):
                sampled = bool(int(parts[2]))
        return sampled

    @classmethod
    def _parse_single_header(
        cls, headers: Headers
    ) -> Optional[BaseTraceContext]:
        # Makes BaseTraceContext from zipkin single header format.
        # https://github.com/openzipkin/b3-propagation

        # b3={TraceId}-{SpanId}-{SamplingState}-{ParentSpanId}
        if headers[cls.SINGLE_HEADER] == "0":
            return None
        payload = headers[cls.SINGLE_HEADER].lower()
        parts: List[str] = payload.split(cls.DELIMITER)
        if len(parts) < 2:
            return None

        debug = cls._parse_debug(parts)
        sampled = debug if debug else cls._parse_sampled(parts)

        context = ZipkinTraceContext(
            trace_id=int(parts[0], 16),
            span_id=int(parts[1], 16),
            parent_id=cls._parse_parent_id(parts),
            sampled=sampled,
            debug=debug,
            shared=False,
        )
        return context

    @classmethod
    def make_context(cls, headers: Headers) -> Optional[BaseTraceContext]:
        """Converts available headers to BaseTraceContext, if headers mapping does
        not contain zipkin headers, function returns None.
        """
        # TODO: add validation for trace_id/span_id/parent_id

        # normalize header names just in case someone passed regular dict
        # instead dict with case insensitive keys
        headers = {k.lower(): v for k, v in headers.items()}

        required = (cls.TRACE_ID_HEADER.lower(), cls.SPAN_ID_HEADER.lower())
        has_b3 = all(h in headers for h in required)
        has_b3_single = cls.SINGLE_HEADER in headers
        debug = cls.parse_debug_header(headers)
        sampled = debug if debug else cls.parse_sampled_header(headers)

        if not (has_b3_single or has_b3):
            return None

        if has_b3:
            try:
                parent_id = int(headers[cls.PARENT_ID_HEADER.lower()], 16)
            except KeyError:
                parent_id = 0
            context = ZipkinTraceContext(
                trace_id=int(headers[cls.TRACE_ID_HEADER.lower()], 16),
                parent_id=parent_id,
                span_id=int(headers[cls.SPAN_ID_HEADER.lower()], 16),
                sampled=sampled,
                debug=debug,
                shared=False,
            )
            return context
        return cls._parse_single_header(headers)


class ZipkinTraceContext(BaseTraceContext):
    @classmethod
    def make_context(cls, headers: Headers) -> Optional[BaseTraceContext]:
        return ZipkinConst.make_context(headers)

    def make_headers(self) -> Headers:
        return ZipkinConst.make_headers(self)

    def make_single_header(self) -> Headers:
        return ZipkinConst.make_single_header(self)
