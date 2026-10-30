#!/usr/bin/env python3
"""Board integration test for UDP fragmentation, retries, and MD5 DMA."""

from __future__ import annotations

import argparse
from pathlib import Path
import random
import socket
import struct
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT / "linux" / "node"
sys.path.insert(0, str(NODE_DIR))
import john_udp_protocol as proto  # noqa: E402

COMMON_HEADER = struct.Struct("<16I")
STATUS_WORDS = struct.Struct("!16I")


class Peer:
    def __init__(self, host: str, port: int, timeout: float = 1.0):
        self.address = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(timeout)
        self.sequence = random.getrandbits(32)

    def close(self):
        self.sock.close()

    def request(self, msg: proto.Message) -> proto.Message:
        self.sock.sendto(msg.encode(), self.address)
        while True:
            data, peer = self.sock.recvfrom(proto.MAX_DATAGRAM + 1)
            if peer != self.address:
                continue
            reply = proto.decode(data)
            if (reply.session, reply.sequence) == (msg.session, msg.sequence):
                return reply

    def next_sequence(self) -> int:
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("response", type=Path)
    parser.add_argument("--host", default="169.254.173.138")
    parser.add_argument("--port", type=int, default=42000)
    args = parser.parse_args()

    request = args.request.read_bytes()
    header = COMMON_HEADER.unpack_from(request)
    if header[:3] != (0x3151544A, 0x00010000, 64):
        raise SystemExit("invalid common request")
    identity = (header[6], header[7], header[8], header[9])
    session = random.getrandbits(32) or 1
    base = dict(
        session=session,
        task_lo=identity[0],
        task_hi=identity[1],
        shard=identity[2],
        batch=identity[3],
    )
    peer = Peer(args.host, args.port)
    try:
        begin = proto.Message(
            proto.BEGIN,
            sequence=peer.next_sequence(),
            total_len=len(request),
            **base,
        )
        assert peer.request(begin).msg_type == proto.ACK

        fragments = [
            (offset, request[offset:offset + proto.MAX_PAYLOAD])
            for offset in range(0, len(request), proto.MAX_PAYLOAD)
        ]

        # Accept a fragment delivered out of order and the same fragment retried.
        offset, payload = fragments[-1]
        last = proto.Message(
            proto.DATA,
            sequence=peer.next_sequence(),
            offset=offset,
            total_len=len(request),
            payload=payload,
            **base,
        )
        assert peer.request(last).msg_type == proto.ACK
        last.sequence = peer.next_sequence()
        assert peer.request(last).msg_type == proto.ACK

        # Reject conflicting retransmission without destroying the valid bytes.
        corrupt = bytes([payload[0] ^ 0xFF]) + payload[1:]
        conflict = proto.Message(
            proto.DATA,
            sequence=peer.next_sequence(),
            offset=offset,
            total_len=len(request),
            payload=corrupt,
            **base,
        )
        reply = peer.request(conflict)
        assert (reply.msg_type, reply.code) == (proto.ERROR, proto.ERR_REQUEST)

        # An early commit must be rejected until all fragments have arrived.
        commit = proto.Message(
            proto.COMMIT,
            sequence=peer.next_sequence(),
            total_len=len(request),
            **base,
        )
        reply = peer.request(commit)
        assert (reply.msg_type, reply.code) == (proto.ERROR, proto.ERR_INCOMPLETE)

        for offset, payload in reversed(fragments[:-1]):
            data = proto.Message(
                proto.DATA,
                sequence=peer.next_sequence(),
                offset=offset,
                total_len=len(request),
                payload=payload,
                **base,
            )
            assert peer.request(data).msg_type == proto.ACK

        commit.sequence = peer.next_sequence()
        assert peer.request(commit).msg_type == proto.ACK

        result_len = 0
        deadline = time.monotonic() + 10.0
        while time.monotonic() < deadline:
            status = proto.Message(
                proto.STATUS,
                sequence=peer.next_sequence(),
                **base,
            )
            reply = peer.request(status)
            values = STATUS_WORDS.unpack(reply.payload)
            if values[8] == proto.STATE_DONE:
                result_len = values[11]
                break
            if values[8] == proto.STATE_ERROR:
                raise RuntimeError("node entered hardware error state")
            time.sleep(0.01)
        if not result_len:
            raise TimeoutError("task did not complete")

        result = bytearray()
        while len(result) < result_len:
            get = proto.Message(
                proto.RESULT,
                sequence=peer.next_sequence(),
                offset=len(result),
                total_len=result_len,
                **base,
            )
            reply = peer.request(get)
            assert reply.msg_type == proto.RESULT_REPLY
            assert reply.offset == len(result)
            result.extend(reply.payload)
        args.response.write_bytes(result)
        print(
            "PASS: out-of-order, duplicate, conflicting duplicate, incomplete "
            f"commit, DMA, and result reassembly ({len(result)} bytes)"
        )
    finally:
        peer.close()


if __name__ == "__main__":
    main()
