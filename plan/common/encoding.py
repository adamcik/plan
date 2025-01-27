# This file is part of the plan timetable generator, see LICENSE for details.


def zig_zag_encode(i: int):
    return (i >> 31) ^ (i << 1)


def zig_zag_decode(i: int):
    return (i >> 1) ^ -(i & 1)


class DeltaDeltaEncoder:
    def __init__(self):
        self.prev: int | None = None
        self.prev_delta: int = 0

    def encode(self, value: int) -> int:
        if self.prev is None:
            self.prev = value
            return value

        delta = value - self.prev
        delta_delta = delta - self.prev_delta

        self.prev = value
        self.prev_delta = delta

        return delta_delta


class DeltaDeltaDecoder:
    def __init__(self):
        self.prev: int | None = None
        self.prev_delta: int = 0

    def decode(self, value: int) -> int:
        if self.prev is None:
            self.prev = value
            return value

        self.prev_delta += value
        self.prev += self.prev_delta
        return self.prev
