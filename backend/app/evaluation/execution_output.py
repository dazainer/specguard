"""Bound combined stdout/stderr in bytes before decoding or retaining logs."""

import re

ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|$))")


def sanitize(data: bytes) -> str:
    text = ANSI.sub("", data.decode("utf-8", errors="replace"))
    return "".join(char for char in text if char in "\n\t" or (ord(char) >= 32 and not 127 <= ord(char) <= 159))


class OutputBuffer:
    def __init__(self, limit: int):
        self.limit = limit
        self.seen = 0
        self.retained = 0
        self.streams = {"stdout": bytearray(), "stderr": bytearray()}

    def add(self, stream: str, data: bytes):
        self.seen += len(data)
        chunk = data[:max(0, self.limit - self.retained)]
        self.streams[stream].extend(chunk)
        self.retained += len(chunk)

    @property
    def truncated(self):
        return self.seen > self.retained

    def text(self, stream: str) -> str:
        # Replacement characters can expand invalid UTF-8; bound encoded text too.
        return sanitize(bytes(self.streams[stream])).encode("utf-8")[:len(self.streams[stream])].decode("utf-8", errors="ignore")
