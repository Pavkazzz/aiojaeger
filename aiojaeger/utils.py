import os
import random
import time
from math import ceil

from aiojaeger.spancontext.jaeger import JaegerConst

rand = random.Random(time.time() * (os.getpid() or 1))


def random_id(bitsize: int = JaegerConst._max_id_bits) -> int:
    return rand.getrandbits(bitsize - 1)


def hexify(i: int) -> str:
    length = ceil(i.bit_length() / 8.0)
    return int(i).to_bytes(length, byteorder="big").hex()
