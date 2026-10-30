"""Binary UDP protocol shared by the AX7020 node and host client."""

from __future__ import annotations

import struct
import zlib

MAGIC = 0x4A4E5031  # "JNP1"
VERSION = 0x00010000
HEADER = struct.Struct("!16I")
HEADER_BYTES = HEADER.size
MAX_DATAGRAM = 1200
MAX_PAYLOAD = MAX_DATAGRAM - HEADER_BYTES

DISCOVER = 1
BEGIN = 2
DATA = 3
COMMIT = 4
STATUS = 5
RESULT = 6
CANCEL = 7
ACK = 8
ERROR = 9
CAPS = 10
STATUS_REPLY = 11
RESULT_REPLY = 12
HEARTBEAT = 13
HEARTBEAT_REPLY = 14
HEALTH = 15
HEALTH_REPLY = 16
RESULT_ACK = 17

STATE_IDLE = 0
STATE_UPLOADING = 1
STATE_QUEUED = 2
STATE_RUNNING = 3
STATE_DONE = 4
STATE_ERROR = 5
STATE_CANCELLED = 6

OK = 0
ERR_HEADER = 1
ERR_CRC = 2
ERR_BUSY = 3
ERR_SESSION = 4
ERR_RANGE = 5
ERR_INCOMPLETE = 6
ERR_REQUEST = 7
ERR_HARDWARE = 8
ERR_NOT_READY = 9
ERR_CANCELLED = 10
ERR_QUEUE_FULL = 11
ERR_RESULT_FULL = 12


class Message:
    __slots__ = (
        "msg_type", "flags", "session", "sequence", "task_lo", "task_hi",
        "shard", "batch", "offset", "total_len", "code", "payload",
    )

    def __init__(self, msg_type, flags=0, session=0, sequence=0, task_lo=0,
                 task_hi=0, shard=0, batch=0, offset=0, total_len=0, code=0,
                 payload=b""):
        self.msg_type = msg_type
        self.flags = flags
        self.session = session
        self.sequence = sequence
        self.task_lo = task_lo
        self.task_hi = task_hi
        self.shard = shard
        self.batch = batch
        self.offset = offset
        self.total_len = total_len
        self.code = code
        self.payload = payload

    def __eq__(self, other):
        return isinstance(other, Message) and all(
            getattr(self, field) == getattr(other, field) for field in self.__slots__
        )

    def __repr__(self):
        fields = ", ".join(
            "{}={!r}".format(field, getattr(self, field)) for field in self.__slots__
        )
        return "Message({})".format(fields)

    @property
    def task(self) -> int:
        return self.task_lo | (self.task_hi << 32)

    def encode(self) -> bytes:
        if len(self.payload) > MAX_PAYLOAD:
            raise ValueError("UDP payload exceeds protocol MTU")
        words = [
            MAGIC,
            VERSION,
            self.msg_type,
            self.flags,
            self.session,
            self.sequence,
            self.task_lo,
            self.task_hi,
            self.shard,
            self.batch,
            self.offset,
            self.total_len,
            len(self.payload),
            zlib.crc32(self.payload) & 0xFFFFFFFF,
            self.code,
            0,
        ]
        prefix = HEADER.pack(*words)
        words[15] = zlib.crc32(prefix[:60]) & 0xFFFFFFFF
        return HEADER.pack(*words) + self.payload


def decode(datagram: bytes) -> Message:
    if len(datagram) < HEADER_BYTES:
        raise ValueError("truncated UDP header")
    words = list(HEADER.unpack_from(datagram))
    if words[0] != MAGIC or words[1] != VERSION:
        raise ValueError("UDP magic/version mismatch")
    header_crc = words[15]
    words[15] = 0
    if zlib.crc32(HEADER.pack(*words)[:60]) & 0xFFFFFFFF != header_crc:
        raise ValueError("UDP header CRC mismatch")
    payload_len = words[12]
    if payload_len > MAX_PAYLOAD or len(datagram) != HEADER_BYTES + payload_len:
        raise ValueError("UDP payload length mismatch")
    payload = datagram[HEADER_BYTES:]
    if zlib.crc32(payload) & 0xFFFFFFFF != words[13]:
        raise ValueError("UDP payload CRC mismatch")
    return Message(
        msg_type=words[2],
        flags=words[3],
        session=words[4],
        sequence=words[5],
        task_lo=words[6],
        task_hi=words[7],
        shard=words[8],
        batch=words[9],
        offset=words[10],
        total_len=words[11],
        code=words[14],
        payload=payload,
    )


def reply(request: Message, msg_type: int, *, code: int = OK,
          payload: bytes = b"", offset: int = 0, total_len: int = 0,
          flags: int = 0) -> Message:
    return Message(
        msg_type=msg_type,
        flags=flags,
        session=request.session,
        sequence=request.sequence,
        task_lo=request.task_lo,
        task_hi=request.task_hi,
        shard=request.shard,
        batch=request.batch,
        offset=offset,
        total_len=total_len,
        code=code,
        payload=payload,
    )
