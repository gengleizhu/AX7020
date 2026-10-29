"""John Packet Communication v2；仅编码协议，不执行密码计算。"""
from collections import namedtuple
from typing import List
import struct

MAX_PAYLOAD = 16 * 65536 - 18


def checksum(data: bytes) -> int:
    return ~sum(int.from_bytes(data[i:i + 4], "little")
                for i in range(0, len(data), 4)) & 0xffffffff


class Packet(namedtuple("_Packet", "type id payload reserved")):
    """不可变报文；兼容PYNQ 2.4的Python 3.6，无dataclasses依赖。"""
    __slots__ = ()

    def __new__(cls, type, id, payload, reserved=b"\0\0\0"):
        return super(Packet, cls).__new__(cls, type, id, payload, reserved)

    def encode(self) -> bytes:
        if not 1 <= self.type <= 255 or not 0 <= self.id <= 65535:
            raise ValueError("invalid packet type/id")
        if not 1 <= len(self.payload) <= MAX_PAYLOAD or len(self.reserved) != 3:
            raise ValueError("invalid payload/reserved length")
        h = (bytes([2, self.type]) + self.reserved[:2]
             + len(self.payload).to_bytes(3, "little") + self.reserved[2:]
             + struct.pack("<H", self.id))
        return h + struct.pack("<I", checksum(h)) + self.payload + struct.pack("<I", checksum(self.payload))


class Decoder:
    """允许任意字节分段；失败后由上层重建会话，不猜测重新同步点。"""
    def __init__(self):
        self.buffer = bytearray()
        self.failed = False

    def feed(self, data: bytes) -> List[Packet]:
        if self.failed:
            raise ValueError("decoder failed; create a new session")
        self.buffer.extend(data)
        packets = []
        try:
            while len(self.buffer) >= 14:
                h = self.buffer[:10]
                n = int.from_bytes(h[4:7], "little")
                if h[0] != 2 or h[1] == 0 or not 1 <= n <= MAX_PAYLOAD:
                    raise ValueError("invalid header")
                if checksum(h) != int.from_bytes(self.buffer[10:14], "little"):
                    raise ValueError("header checksum")
                if len(self.buffer) < n + 18:
                    break
                payload = bytes(self.buffer[14:14+n])
                if checksum(payload) != int.from_bytes(self.buffer[14+n:18+n], "little"):
                    raise ValueError("payload checksum")
                packets.append(Packet(h[1], int.from_bytes(h[8:10], "little"),
                                      payload, bytes(h[2:4] + h[7:8])))
                del self.buffer[:18+n]
        except ValueError:
            self.failed = True
            raise
        return packets
