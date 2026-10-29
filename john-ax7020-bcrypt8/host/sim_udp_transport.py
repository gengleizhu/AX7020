"""离线验证专用UDP封装。只绑定回环地址，不提供远程配置/bitstream功能。

可靠性：带CRC的分片、Session/请求ID、乱序去重、缺片查询重传、
幂等COMMIT及结果分片拉取。不是生产板端UDP服务。
"""
import dataclasses
import struct
import zlib

HEADER = struct.Struct("<4sBBQIHHIH")
MAGIC = b"JRTL"
VERSION = 1
MAX_TOTAL = 1048576
CHUNK = 1200
DATA, COMMIT, POLL, GET, REPLY, ERROR = range(1, 7)


@dataclasses.dataclass
class Frame:
    kind: int
    session: int
    request: int
    index: int = 0
    count: int = 1
    total: int = 0
    payload: bytes = b""

    def encode(self):
        header = HEADER.pack(MAGIC, VERSION, self.kind, self.session, self.request,
                             self.index, self.count, self.total, len(self.payload))
        raw = header + self.payload
        return raw + struct.pack("<I", zlib.crc32(raw))

    @classmethod
    def decode(cls, raw):
        if len(raw) < HEADER.size + 4:
            raise ValueError("short datagram")
        magic, version, kind, session, request, index, count, total, length = HEADER.unpack(raw[:HEADER.size])
        if magic != MAGIC or version != VERSION or kind not in range(1, 7):
            raise ValueError("header")
        if length > CHUNK or len(raw) != HEADER.size + length + 4 or total > MAX_TOTAL:
            raise ValueError("length")
        if not 1 <= count <= 16384 or not 0 <= index < count:
            raise ValueError("fragment")
        if zlib.crc32(raw[:-4]) != struct.unpack("<I", raw[-4:])[0]:
            raise ValueError("crc")
        return cls(kind, session, request, index, count, total, raw[HEADER.size:-4])


class Assembly:
    def __init__(self, frame):
        self.session, self.request = frame.session, frame.request
        self.count, self.total = frame.count, frame.total
        self.parts = {}

    def add(self, frame):
        if (frame.session, frame.request, frame.count, frame.total) != (
                self.session, self.request, self.count, self.total):
            raise ValueError("changed transfer")
        if frame.index in self.parts and self.parts[frame.index] != frame.payload:
            raise ValueError("conflicting duplicate")
        self.parts[frame.index] = frame.payload
        if sum(map(len, self.parts.values())) > self.total:
            raise ValueError("total exceeded")

    def missing(self):
        return [i for i in range(self.count) if i not in self.parts]

    def finish(self):
        if self.missing():
            raise ValueError("incomplete")
        raw = b"".join(self.parts[i] for i in range(self.count))
        if len(raw) != self.total:
            raise ValueError("total mismatch")
        return raw
