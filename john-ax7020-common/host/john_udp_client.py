#!/usr/bin/env python3
"""Reliable host client for the AX7020 persistent UDP node service."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import socket
import struct
import sys
import time

COMMON_HEADER = struct.Struct("<16I")
STATUS_WORDS = struct.Struct("!16I")

THIS_DIR = Path(__file__).resolve().parent
NODE_DIR = THIS_DIR.parent / "linux" / "node"
sys.path.insert(0, str(NODE_DIR))
import john_udp_protocol as proto  # noqa: E402


class Client:
    def __init__(self, host: str, port: int, timeout: float, retries: int):
        self.peer = (host, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.timeout = timeout
        self.sock.settimeout(timeout)
        self.retries = retries
        self.sequence = random.getrandbits(32)

    def close(self):
        self.sock.close()

    def _next_sequence(self):
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        return self.sequence

    def exchange(self, message: proto.Message, expected):
        encoded = message.encode()
        last_error = None
        for _ in range(self.retries):
            self.sock.settimeout(self.timeout)
            self.sock.sendto(encoded, self.peer)
            deadline = time.monotonic() + self.timeout
            while True:
                left = deadline - time.monotonic()
                if left <= 0:
                    last_error = TimeoutError("UDP response timeout")
                    break
                self.sock.settimeout(left)
                try:
                    datagram, peer = self.sock.recvfrom(proto.MAX_DATAGRAM + 1)
                except socket.timeout as exc:
                    last_error = exc
                    break
                if peer[0] != self.peer[0] or peer[1] != self.peer[1]:
                    continue
                try:
                    response = proto.decode(datagram)
                except ValueError:
                    continue
                if (response.session, response.sequence) != (
                    message.session, message.sequence
                ):
                    continue
                if response.msg_type == proto.ERROR:
                    raise RuntimeError(f"node error code={response.code}")
                if response.msg_type not in expected:
                    raise RuntimeError(
                        f"unexpected response type {response.msg_type}"
                    )
                return response
        raise TimeoutError(f"node did not reply after {self.retries} attempts") from last_error

    def discover(self):
        msg = proto.Message(
            msg_type=proto.DISCOVER,
            session=0,
            sequence=self._next_sequence(),
        )
        return self.exchange(msg, {proto.CAPS})

    def status(self, session=0, identity=(0, 0, 0, 0)):
        task_lo, task_hi, shard, batch = identity
        msg = proto.Message(
            msg_type=proto.STATUS,
            session=session,
            sequence=self._next_sequence(),
            task_lo=task_lo,
            task_hi=task_hi,
            shard=shard,
            batch=batch,
        )
        return self.exchange(msg, {proto.STATUS_REPLY})

    def run(self, request: bytes, poll_interval: float):
        if len(request) < 64:
            raise ValueError("truncated common request")
        header = COMMON_HEADER.unpack_from(request)
        if header[:3] != (0x3151544A, 0x00010000, 64) or header[3] != len(request):
            raise ValueError("invalid common request")
        session = random.getrandbits(32) or 1
        identity = (header[6], header[7], header[8], header[9])
        base = dict(
            session=session,
            task_lo=identity[0],
            task_hi=identity[1],
            shard=identity[2],
            batch=identity[3],
        )
        begin = proto.Message(
            msg_type=proto.BEGIN,
            sequence=self._next_sequence(),
            total_len=len(request),
            **base,
        )
        self.exchange(begin, {proto.ACK})

        for offset in range(0, len(request), proto.MAX_PAYLOAD):
            chunk = request[offset:offset + proto.MAX_PAYLOAD]
            data = proto.Message(
                msg_type=proto.DATA,
                sequence=self._next_sequence(),
                offset=offset,
                total_len=len(request),
                payload=chunk,
                **base,
            )
            self.exchange(data, {proto.ACK})

        commit = proto.Message(
            msg_type=proto.COMMIT,
            sequence=self._next_sequence(),
            total_len=len(request),
            **base,
        )
        self.exchange(commit, {proto.ACK})

        while True:
            response = self.status(session, identity)
            status = parse_status(response.payload)
            if status["service_state"] == proto.STATE_DONE:
                result_len = status["result_bytes"]
                break
            if status["service_state"] == proto.STATE_ERROR:
                raise RuntimeError("node entered hardware error state")
            time.sleep(poll_interval)

        result = bytearray()
        while len(result) < result_len:
            get = proto.Message(
                msg_type=proto.RESULT,
                sequence=self._next_sequence(),
                offset=len(result),
                total_len=result_len,
                **base,
            )
            response = self.exchange(get, {proto.RESULT_REPLY})
            if response.offset != len(result) or response.total_len != result_len:
                raise RuntimeError("result fragment offset/length mismatch")
            if not response.payload:
                raise RuntimeError("empty result fragment")
            result.extend(response.payload)
        return bytes(result), status


def parse_status(payload: bytes):
    if len(payload) != STATUS_WORDS.size:
        raise ValueError("invalid node status payload")
    values = STATUS_WORDS.unpack(payload)
    return {
        "register_abi": values[0],
        "stream_abi": values[1],
        "algorithm": values[2],
        "units": values[3],
        "cores_per_unit": values[4],
        "clock_hz": values[5],
        "capabilities": values[6],
        "pl_status": values[7],
        "service_state": values[8],
        "received_bytes": values[9],
        "request_bytes": values[10],
        "result_bytes": values[11],
        "completed": values[12] | (values[13] << 32),
        "elapsed_cycles": values[14] | (values[15] << 32),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="169.254.173.138")
    parser.add_argument("--port", type=int, default=42000)
    parser.add_argument("--timeout", type=float, default=0.5)
    parser.add_argument("--retries", type=int, default=5)
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("discover")
    run = sub.add_parser("run")
    run.add_argument("request", type=Path)
    run.add_argument("response", type=Path)
    run.add_argument("--poll-interval", type=float, default=0.01)
    args = parser.parse_args()

    client = Client(args.host, args.port, args.timeout, args.retries)
    try:
        if args.action == "discover":
            print(json.dumps(parse_status(client.discover().payload), indent=2))
        else:
            response, status = client.run(
                args.request.read_bytes(), args.poll_interval
            )
            args.response.write_bytes(response)
            print(json.dumps(status, indent=2))
    finally:
        client.close()


if __name__ == "__main__":
    main()
