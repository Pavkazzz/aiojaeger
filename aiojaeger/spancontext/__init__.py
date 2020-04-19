# possible span kinds
import abc
from typing import Optional

from pydantic import BaseModel

from aiojaeger.mypy_types import Headers

CLIENT = "CLIENT"
SERVER = "SERVER"
PRODUCER = "PRODUCER"
CONSUMER = "CONSUMER"


class BaseTraceContext(BaseModel):
    """Immutable class with trace related data that travels across
    process boundaries.
    """

    trace_id: int
    span_id: int
    parent_id: int = 0
    sampled: Optional[bool] = None
    debug: bool = False
    debug_id: Optional[str] = None
    shared: bool

    @property
    def name(self) -> str:
        return f"{self.trace_id}:{self.span_id}:{self.parent_id}"

    @abc.abstractmethod
    def make_headers(self) -> Headers:
        """Creates dict with headers from available context.

        Resulting dict should be passed to HTTP client  propagate contest
        to other services.
        """
        pass

    @classmethod
    @abc.abstractmethod
    def make_context(cls, headers: Headers) -> Optional["BaseTraceContext"]:
        pass


class DummyTraceContext(BaseTraceContext):
    def make_headers(self) -> Headers:
        return {}

    @classmethod
    def make_context(
        cls, headers: Headers, sampled: bool = True
    ) -> BaseTraceContext:
        return cls(
            trace_id=1,
            span_id=2,
            parent_id=0,
            debug=False,
            sampled=sampled,
            shared=False,
        )
