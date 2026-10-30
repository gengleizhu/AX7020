#!/usr/bin/env python3
"""Persistent UDP-to-AXI-DMA service for one AX7020 accelerator node."""

from __future__ import annotations

import argparse
import ctypes
import logging
import socket
import struct
import threading
import time

import john_udp_protocol as proto

REGISTER_ABI = 0x00010001
STREAM_MAGIC = 0x3151544A
STREAM_ABI = 0x00010000
MAX_REQUEST = 64 + 65536
MAX_RESPONSE = 64 + 8192
COMMON_HEADER = struct.Struct("<16I")
STATUS_WORDS = struct.Struct("!16I")


class HwIdentity(ctypes.Structure):
    _fields_ = [
        ("algorithm", ctypes.c_uint32),
        ("units", ctypes.c_uint32),
        ("cores", ctypes.c_uint32),
        ("clock_hz", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class HwMetrics(ctypes.Structure):
    _fields_ = [
        ("completed_lo", ctypes.c_uint32),
        ("completed_hi", ctypes.c_uint32),
        ("cycles_lo", ctypes.c_uint32),
        ("cycles_hi", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class Hardware:
    def __init__(self, library_path: str = "/usr/lib/libjohnhw.so"):
        self.lib = ctypes.CDLL(library_path)
        self.lib.john_hw_open.restype = ctypes.c_void_p
        self.lib.john_hw_open.argtypes = [
            ctypes.c_char_p, ctypes.c_char_p, ctypes.c_size_t
        ]
        self.lib.john_hw_close.argtypes = [ctypes.c_void_p]
        self.lib.john_hw_identify.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(HwIdentity),
            ctypes.c_char_p, ctypes.c_size_t,
        ]
        self.lib.john_hw_run.argtypes = [
            ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
            ctypes.c_void_p, ctypes.c_uint32, ctypes.POINTER(ctypes.c_uint32),
            ctypes.c_uint32, ctypes.POINTER(HwMetrics),
            ctypes.c_char_p, ctypes.c_size_t,
        ]
        error = ctypes.create_string_buffer(256)
        self.handle = self.lib.john_hw_open(b"/dev/john-dma", error, len(error))
        if not self.handle:
            raise RuntimeError(error.value.decode("utf-8", "replace"))
        self.max_tx = MAX_REQUEST
        self.max_rx = MAX_RESPONSE
        self.identity = self.identify()

    def close(self):
        if self.handle:
            self.lib.john_hw_close(self.handle)
            self.handle = None

    def identify(self):
        identity = HwIdentity()
        error = ctypes.create_string_buffer(256)
        if self.lib.john_hw_identify(
            self.handle, ctypes.byref(identity), error, len(error)
        ):
            raise RuntimeError(error.value.decode("utf-8", "replace"))
        return {
            "algorithm": identity.algorithm,
            "units": identity.units,
            "cores": identity.cores,
            "clock_hz": identity.clock_hz,
            "capabilities": identity.capabilities,
            "status": identity.status,
        }

    def validate_request(self, request: bytes):
        if not 64 <= len(request) <= min(MAX_REQUEST, self.max_tx):
            raise ValueError("common request length out of range")
        header = COMMON_HEADER.unpack_from(request)
        if (header[0], header[1], header[2], header[3]) != (
            STREAM_MAGIC, STREAM_ABI, 64, len(request)
        ):
            raise ValueError("common request header/length mismatch")
        if header[14] or header[15]:
            raise ValueError("common request reserved words are nonzero")
        if header[4] != self.identity["algorithm"]:
            raise ValueError("request algorithm does not match bitstream")
        response_len = 64 + header[12]
        if not 64 <= response_len <= min(MAX_RESPONSE, self.max_rx):
            raise ValueError("common response length out of range")
        return header, response_len

    def run(self, request: bytes, timeout_ms: int):
        _, expected_len = self.validate_request(request)
        request_buffer = ctypes.create_string_buffer(request)
        response_buffer = ctypes.create_string_buffer(expected_len)
        actual_len = ctypes.c_uint32()
        metrics = HwMetrics()
        error = ctypes.create_string_buffer(512)
        rc = self.lib.john_hw_run(
            self.handle, request_buffer, len(request), response_buffer,
            expected_len, ctypes.byref(actual_len), timeout_ms,
            ctypes.byref(metrics), error, len(error),
        )
        if rc:
            raise RuntimeError(error.value.decode("utf-8", "replace"))
        return response_buffer.raw[:actual_len.value], {
            "completed_lo": metrics.completed_lo,
            "completed_hi": metrics.completed_hi,
            "cycles_lo": metrics.cycles_lo,
            "cycles_hi": metrics.cycles_hi,
            "status": metrics.status,
        }


class Node:
    def __init__(self, hardware: Hardware, timeout_ms: int):
        self.hw = hardware
        self.timeout_ms = timeout_ms
        self.lock = threading.Lock()
        self.condition = threading.Condition(self.lock)
        self.state = proto.STATE_IDLE
        self.session = 0
        self.task_lo = self.task_hi = self.shard = self.batch = 0
        self.request = bytearray()
        self.seen = bytearray()
        self.received = 0
        self.result = b""
        self.error_code = proto.OK
        self.error_text = ""
        self.metrics = {}
        self.stop = False
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def close(self):
        with self.condition:
            self.stop = True
            self.condition.notify_all()
        self.worker.join(timeout=2)
        self.hw.close()

    def _matches(self, msg):
        return (
            msg.session == self.session
            and msg.task_lo == self.task_lo
            and msg.task_hi == self.task_hi
            and msg.shard == self.shard
            and msg.batch == self.batch
        )

    def begin(self, msg):
        if not 64 <= msg.total_len <= min(MAX_REQUEST, self.hw.max_tx):
            return proto.ERR_RANGE
        with self.condition:
            if self.state in (proto.STATE_QUEUED, proto.STATE_RUNNING):
                return proto.ERR_BUSY
            if self.state == proto.STATE_UPLOADING and self._matches(msg):
                return proto.OK
            self.session = msg.session
            self.task_lo, self.task_hi = msg.task_lo, msg.task_hi
            self.shard, self.batch = msg.shard, msg.batch
            self.request = bytearray(msg.total_len)
            self.seen = bytearray(msg.total_len)
            self.received = 0
            self.result = b""
            self.error_code = proto.OK
            self.error_text = ""
            self.metrics = {}
            self.state = proto.STATE_UPLOADING
            return proto.OK

    def data(self, msg):
        with self.lock:
            if self.state != proto.STATE_UPLOADING or not self._matches(msg):
                return proto.ERR_SESSION
            end = msg.offset + len(msg.payload)
            if msg.total_len != len(self.request) or end > len(self.request):
                return proto.ERR_RANGE
            for index, value in enumerate(msg.payload, msg.offset):
                if self.seen[index] and self.request[index] != value:
                    return proto.ERR_REQUEST
                if not self.seen[index]:
                    self.seen[index] = 1
                    self.received += 1
                    self.request[index] = value
            return proto.OK

    def commit(self, msg):
        with self.condition:
            if self._matches(msg) and self.state in (
                proto.STATE_QUEUED, proto.STATE_RUNNING, proto.STATE_DONE
            ):
                return proto.OK
            if self.state != proto.STATE_UPLOADING or not self._matches(msg):
                return proto.ERR_SESSION
            if self.received != len(self.request):
                return proto.ERR_INCOMPLETE
            try:
                header, _ = self.hw.validate_request(self.request)
            except (ValueError, RuntimeError):
                return proto.ERR_REQUEST
            if (header[6], header[7], header[8], header[9]) != (
                self.task_lo, self.task_hi, self.shard, self.batch
            ):
                return proto.ERR_REQUEST
            self.state = proto.STATE_QUEUED
            self.condition.notify()
            return proto.OK

    def cancel(self, msg):
        with self.condition:
            if not self._matches(msg):
                return proto.ERR_SESSION
            if self.state == proto.STATE_RUNNING:
                return proto.ERR_BUSY
            self.state = proto.STATE_IDLE
            self.request = bytearray()
            self.seen = bytearray()
            self.result = b""
            self.error_code = proto.ERR_CANCELLED
            return proto.OK

    def _worker(self):
        while True:
            with self.condition:
                self.condition.wait_for(
                    lambda: self.stop or self.state == proto.STATE_QUEUED
                )
                if self.stop:
                    return
                self.state = proto.STATE_RUNNING
                request = bytes(self.request)
            try:
                result, metrics = self.hw.run(request, self.timeout_ms)
            except Exception as exc:  # hardware errors must become node state
                logging.exception("hardware task failed")
                with self.lock:
                    self.state = proto.STATE_ERROR
                    self.error_code = proto.ERR_HARDWARE
                    self.error_text = str(exc)[:160]
            else:
                with self.lock:
                    self.result = result
                    self.metrics = metrics
                    self.state = proto.STATE_DONE

    def status_payload(self):
        with self.lock:
            ident = self.hw.identify()
            completed = (
                self.metrics.get("completed_lo", 0)
                | (self.metrics.get("completed_hi", 0) << 32)
            )
            cycles = (
                self.metrics.get("cycles_lo", 0)
                | (self.metrics.get("cycles_hi", 0) << 32)
            )
            return STATUS_WORDS.pack(
                REGISTER_ABI,
                STREAM_ABI,
                ident["algorithm"],
                ident["units"],
                ident["cores"],
                ident["clock_hz"],
                ident["capabilities"],
                ident["status"],
                self.state,
                self.received,
                len(self.request),
                len(self.result),
                completed & 0xFFFFFFFF,
                completed >> 32,
                cycles & 0xFFFFFFFF,
                cycles >> 32,
            )


def serve(bind: str, port: int, timeout_ms: int):
    hardware = Hardware()
    node = Node(hardware, timeout_ms)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((bind, port))
    logging.info("john-node listening on %s:%d: %s", bind, port, hardware.identity)
    try:
        while True:
            datagram, peer = sock.recvfrom(proto.MAX_DATAGRAM + 1)
            try:
                msg = proto.decode(datagram)
            except ValueError as exc:
                logging.warning("drop malformed datagram from %s: %s", peer, exc)
                continue

            if msg.msg_type == proto.DISCOVER:
                response = proto.reply(
                    msg, proto.CAPS, payload=node.status_payload(), code=proto.OK
                )
            elif msg.msg_type == proto.BEGIN:
                code = node.begin(msg)
                response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR,
                                       code=code)
            elif msg.msg_type == proto.DATA:
                code = node.data(msg)
                response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR,
                                       code=code, offset=msg.offset,
                                       total_len=msg.total_len)
            elif msg.msg_type == proto.COMMIT:
                code = node.commit(msg)
                response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR,
                                       code=code)
            elif msg.msg_type == proto.STATUS:
                response = proto.reply(msg, proto.STATUS_REPLY,
                                       payload=node.status_payload(), code=proto.OK)
            elif msg.msg_type == proto.RESULT:
                with node.lock:
                    if not node._matches(msg):
                        code, payload, total = proto.ERR_SESSION, b"", 0
                    elif node.state != proto.STATE_DONE:
                        code, payload, total = proto.ERR_NOT_READY, b"", len(node.result)
                    elif msg.offset >= len(node.result):
                        code, payload, total = proto.ERR_RANGE, b"", len(node.result)
                    else:
                        code = proto.OK
                        total = len(node.result)
                        payload = node.result[msg.offset:msg.offset + proto.MAX_PAYLOAD]
                response = proto.reply(
                    msg, proto.RESULT_REPLY if code == 0 else proto.ERROR,
                    code=code, payload=payload, offset=msg.offset, total_len=total
                )
            elif msg.msg_type == proto.CANCEL:
                code = node.cancel(msg)
                response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR,
                                       code=code)
            else:
                response = proto.reply(msg, proto.ERROR, code=proto.ERR_HEADER)
            sock.sendto(response.encode(), peer)
    finally:
        node.close()
        sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=42000)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper()),
        format="%(asctime)s %(levelname)s %(message)s",
    )
    serve(args.bind, args.port, args.timeout_ms)


if __name__ == "__main__":
    main()
