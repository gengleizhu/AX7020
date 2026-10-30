#!/usr/bin/env python3
"""Persistent queued UDP-to-AXI-DMA service for one AX7020 node."""

from __future__ import annotations

from collections import OrderedDict, deque
import argparse
import ctypes
import json
import logging
import socket
import struct
import threading
import time

import john_health
import john_udp_protocol as proto

REGISTER_ABI = 0x00010001
STREAM_MAGIC = 0x3151544A
STREAM_ABI = 0x00010000
HEALTH_ABI = 0x00010000
MAX_REQUEST = 64 + 65536
MAX_RESPONSE = 64 + 8192
COMMON_HEADER = struct.Struct("<16I")
STATUS_WORDS = struct.Struct("!16I")
HEARTBEAT_WORDS = struct.Struct("!12I")

LOAD_NOT_LOADED = 0
LOAD_LOADING = 1
LOAD_INITIALIZING = 2
LOAD_READY = 3
LOAD_FAILED = 4
LOAD_NEED_RELOAD = 5


class HwIdentity(ctypes.Structure):
    _fields_ = [
        ("algorithm", ctypes.c_uint32),
        ("units", ctypes.c_uint32),
        ("cores", ctypes.c_uint32),
        ("clock_hz", ctypes.c_uint32),
        ("capabilities", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
        ("build_date", ctypes.c_uint32),
        ("register_abi", ctypes.c_uint32),
        ("stream_abi", ctypes.c_uint32),
        ("native_status", ctypes.c_uint32),
    ]


class HwMetrics(ctypes.Structure):
    _fields_ = [
        ("completed_lo", ctypes.c_uint32),
        ("completed_hi", ctypes.c_uint32),
        ("cycles_lo", ctypes.c_uint32),
        ("cycles_hi", ctypes.c_uint32),
        ("status", ctypes.c_uint32),
    ]


class HwDmaStats(ctypes.Structure):
    _fields_ = [
        ("tx_completions", ctypes.c_uint64),
        ("rx_completions", ctypes.c_uint64),
        ("running", ctypes.c_uint32),
        ("reserved", ctypes.c_uint32),
    ]


class Hardware:
    def __init__(self, library_path="/usr/lib/libjohnhw.so"):
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
        self.lib.john_hw_dma_stats.argtypes = [
            ctypes.c_void_p, ctypes.POINTER(HwDmaStats),
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
        return {field: getattr(identity, field) for field, _ in HwIdentity._fields_}

    def dma_stats(self):
        stats = HwDmaStats()
        error = ctypes.create_string_buffer(256)
        if self.lib.john_hw_dma_stats(
            self.handle, ctypes.byref(stats), error, len(error)
        ):
            raise RuntimeError(error.value.decode("utf-8", "replace"))
        return {
            "tx_completions": stats.tx_completions,
            "rx_completions": stats.rx_completions,
            "running": stats.running,
        }

    def validate_request(self, request):
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

    def run(self, request, timeout_ms):
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
            field: getattr(metrics, field) for field, _ in HwMetrics._fields_
        }


class Task:
    __slots__ = (
        "key", "session", "task_lo", "task_hi", "shard", "batch",
        "state", "request", "request_len", "seen", "received", "result", "metrics",
        "error_code", "created", "updated",
    )

    def __init__(self, msg):
        self.key = task_key(msg)
        self.session = msg.session
        self.task_lo = msg.task_lo
        self.task_hi = msg.task_hi
        self.shard = msg.shard
        self.batch = msg.batch
        self.state = proto.STATE_UPLOADING
        self.request = bytearray(msg.total_len)
        self.request_len = msg.total_len
        self.seen = bytearray(msg.total_len)
        self.received = 0
        self.result = b""
        self.metrics = {}
        self.error_code = proto.OK
        self.created = time.monotonic()
        self.updated = self.created


def task_key(msg):
    return (msg.session, msg.task_lo, msg.task_hi, msg.shard, msg.batch)


def task_name(task):
    task_id = task.task_lo | (task.task_hi << 32)
    return f"{task.session:08x}:{task_id:016x}:{task.shard}:{task.batch}"


class Node:
    def __init__(self, hardware, timeout_ms, queue_depth, result_depth,
                 result_ttl, interface, node_id):
        self.hw = hardware
        self.timeout_ms = timeout_ms
        self.queue_depth = queue_depth
        self.result_depth = result_depth
        self.result_ttl = result_ttl
        self.node_id = node_id
        self.started = time.monotonic()
        self.condition = threading.Condition()
        self.tasks = OrderedDict()
        self.pending = deque()
        self.running_key = None
        self.heartbeat_sequence = 0
        self.stop = False
        self.health = john_health.HealthMonitor(interface)
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def close(self):
        with self.condition:
            self.stop = True
            self.condition.notify_all()
        self.worker.join(timeout=2)
        self.health.close()
        self.hw.close()

    def _cleanup_locked(self):
        now = time.monotonic()
        terminal = (proto.STATE_DONE, proto.STATE_ERROR, proto.STATE_CANCELLED)
        expired = [
            key for key, task in self.tasks.items()
            if task.state in terminal and now - task.updated > self.result_ttl
        ]
        for key in expired:
            task = self.tasks.pop(key)
            logging.warning("expired task state/result %s", task_name(task))

    def _active_count_locked(self):
        return sum(
            task.state in (
                proto.STATE_UPLOADING, proto.STATE_QUEUED, proto.STATE_RUNNING
            ) for task in self.tasks.values()
        )

    def _result_count_locked(self):
        return sum(task.state == proto.STATE_DONE for task in self.tasks.values())

    def begin(self, msg):
        if not 64 <= msg.total_len <= min(MAX_REQUEST, self.hw.max_tx):
            return proto.ERR_RANGE
        key = task_key(msg)
        with self.condition:
            self._cleanup_locked()
            existing = self.tasks.get(key)
            if existing:
                if existing.request_len != msg.total_len:
                    return proto.ERR_REQUEST
                return proto.OK if existing.state == proto.STATE_UPLOADING else proto.ERR_BUSY
            if self._active_count_locked() >= self.queue_depth:
                return proto.ERR_QUEUE_FULL
            self.tasks[key] = Task(msg)
            return proto.OK

    def data(self, msg):
        with self.condition:
            task = self.tasks.get(task_key(msg))
            if not task or task.state != proto.STATE_UPLOADING:
                return proto.ERR_SESSION
            end = msg.offset + len(msg.payload)
            if msg.total_len != len(task.request) or end > len(task.request):
                return proto.ERR_RANGE
            for index, value in enumerate(msg.payload, msg.offset):
                if task.seen[index] and task.request[index] != value:
                    return proto.ERR_REQUEST
                if not task.seen[index]:
                    task.seen[index] = 1
                    task.received += 1
                    task.request[index] = value
            task.updated = time.monotonic()
            return proto.OK

    def commit(self, msg):
        with self.condition:
            task = self.tasks.get(task_key(msg))
            if not task:
                return proto.ERR_SESSION
            if task.state in (proto.STATE_QUEUED, proto.STATE_RUNNING, proto.STATE_DONE):
                return proto.OK
            if task.state != proto.STATE_UPLOADING:
                return proto.ERR_SESSION
            if task.received != len(task.request):
                return proto.ERR_INCOMPLETE
            try:
                header, _ = self.hw.validate_request(task.request)
            except (ValueError, RuntimeError):
                logging.exception("invalid task request %s", task_name(task))
                return proto.ERR_REQUEST
            if (header[6], header[7], header[8], header[9]) != (
                task.task_lo, task.task_hi, task.shard, task.batch
            ):
                return proto.ERR_REQUEST
            task.state = proto.STATE_QUEUED
            task.updated = time.monotonic()
            self.pending.append(task.key)
            self.condition.notify_all()
            logging.debug("queued task %s depth=%d", task_name(task), len(self.pending))
            return proto.OK

    def cancel(self, msg):
        key = task_key(msg)
        with self.condition:
            task = self.tasks.get(key)
            if not task:
                return proto.ERR_SESSION
            if task.state == proto.STATE_RUNNING:
                return proto.ERR_BUSY
            if task.state == proto.STATE_QUEUED:
                try:
                    self.pending.remove(key)
                except ValueError:
                    pass
            task.state = proto.STATE_CANCELLED
            task.request = bytearray()
            task.seen = bytearray()
            task.result = b""
            task.error_code = proto.ERR_CANCELLED
            task.updated = time.monotonic()
            self.condition.notify_all()
            logging.debug("cancelled task %s", task_name(task))
            return proto.OK

    def release_result(self, msg):
        key = task_key(msg)
        with self.condition:
            task = self.tasks.get(key)
            if not task:
                # RESULT_ACK is idempotent: an ACK retry after the first
                # release must not turn a successfully consumed result into
                # an apparent task failure.
                return proto.OK
            if task.state != proto.STATE_DONE:
                return proto.ERR_NOT_READY
            del self.tasks[key]
            self.condition.notify_all()
            logging.debug("released result %s", task_name(task))
            return proto.OK

    def result_fragment(self, msg):
        with self.condition:
            task = self.tasks.get(task_key(msg))
            if not task:
                return proto.ERR_SESSION, b"", 0
            if task.state != proto.STATE_DONE:
                return proto.ERR_NOT_READY, b"", len(task.result)
            if msg.offset >= len(task.result):
                return proto.ERR_RANGE, b"", len(task.result)
            return (proto.OK,
                    task.result[msg.offset:msg.offset + proto.MAX_PAYLOAD],
                    len(task.result))

    def _worker_ready_locked(self):
        return self.pending and self._result_count_locked() < self.result_depth

    def _worker(self):
        while True:
            with self.condition:
                self.condition.wait_for(lambda: self.stop or self._worker_ready_locked())
                if self.stop:
                    return
                key = self.pending.popleft()
                task = self.tasks.get(key)
                if not task or task.state != proto.STATE_QUEUED:
                    continue
                task.state = proto.STATE_RUNNING
                task.updated = time.monotonic()
                self.running_key = key
                request = bytes(task.request)
                logging.debug("running task %s", task_name(task))
            try:
                result, metrics = self.hw.run(request, self.timeout_ms)
            except Exception:
                logging.exception("hardware task failed %s", task_name(task))
                with self.condition:
                    task.state = proto.STATE_ERROR
                    task.error_code = proto.ERR_HARDWARE
                    task.updated = time.monotonic()
                    self.running_key = None
                    self.condition.notify_all()
            else:
                with self.condition:
                    task.result = result
                    task.metrics = metrics
                    task.state = proto.STATE_DONE
                    task.updated = time.monotonic()
                    task.request = bytearray()
                    task.seen = bytearray()
                    self.running_key = None
                    self.condition.notify_all()
                    completed = metrics["completed_lo"] | (metrics["completed_hi"] << 32)
                    cycles = metrics["cycles_lo"] | (metrics["cycles_hi"] << 32)
                    logging.debug("completed task %s records=%d cycles=%d result=%d",
                                  task_name(task), completed, cycles, len(result))

    @staticmethod
    def _load_state(identity):
        status = identity["status"]
        if status & (1 << 5):
            return LOAD_NEED_RELOAD
        if status & (1 << 3):
            return LOAD_FAILED
        if status & (1 << 4):
            return LOAD_READY
        return LOAD_NOT_LOADED

    def _node_state_locked(self):
        if self.running_key:
            return proto.STATE_RUNNING
        if self.pending:
            return proto.STATE_QUEUED
        if any(t.state == proto.STATE_UPLOADING for t in self.tasks.values()):
            return proto.STATE_UPLOADING
        return proto.STATE_IDLE

    def status_payload(self, msg=None):
        with self.condition:
            self._cleanup_locked()
            task = self.tasks.get(task_key(msg)) if msg and msg.session else None
            if msg and msg.session and not task:
                return None
            state = task.state if task else self._node_state_locked()
            received = task.received if task else 0
            request_bytes = task.request_len if task else 0
            result_bytes = len(task.result) if task else 0
            metrics = dict(task.metrics) if task else {}
        identity = self.hw.identify()
        completed = metrics.get("completed_lo", 0) | (metrics.get("completed_hi", 0) << 32)
        cycles = metrics.get("cycles_lo", 0) | (metrics.get("cycles_hi", 0) << 32)
        return STATUS_WORDS.pack(
            identity["register_abi"], identity["stream_abi"],
            identity["algorithm"], identity["units"], identity["cores"],
            identity["clock_hz"], identity["capabilities"], identity["status"],
            state, received, request_bytes, result_bytes,
            completed & 0xFFFFFFFF, completed >> 32,
            cycles & 0xFFFFFFFF, cycles >> 32,
        )

    def heartbeat_payload(self):
        identity = self.hw.identify()
        dma = self.hw.dma_stats()
        with self.condition:
            self._cleanup_locked()
            self.heartbeat_sequence = (self.heartbeat_sequence + 1) & 0xFFFFFFFF
            values = (self.heartbeat_sequence, self._node_state_locked(),
                      len(self.pending), self._result_count_locked())
        return HEARTBEAT_WORDS.pack(
            HEALTH_ABI, values[0], int(time.monotonic() - self.started), values[1],
            values[2], values[3], self._load_state(identity), identity["status"],
            identity["algorithm"], identity["build_date"],
            dma["tx_completions"] & 0xFFFFFFFF,
            dma["rx_completions"] & 0xFFFFFFFF,
        )

    def health_payload(self):
        identity = self.hw.identify()
        dma = self.hw.dma_stats()
        sampled = self.health.snapshot()
        with self.condition:
            self._cleanup_locked()
            running = self.tasks.get(self.running_key)
            service = {
                "uptime_s": int(time.monotonic() - self.started),
                "state": self._node_state_locked(),
                "queue_capacity": self.queue_depth,
                "queued": len(self.pending),
                "result_capacity": self.result_depth,
                "results_cached": self._result_count_locked(),
                "tasks_tracked": len(self.tasks),
                "running_task": task_name(running) if running else "",
            }
        payload = {
            "health_abi": HEALTH_ABI, "node_id": self.node_id, **sampled,
            "dma": dma,
            "bitstream": {
                "build_date": identity["build_date"],
                "register_abi": identity["register_abi"],
                "stream_abi": identity["stream_abi"],
                "algorithm": identity["algorithm"],
                "units": identity["units"],
                "cores_per_unit": identity["cores"],
                "clock_hz": identity["clock_hz"],
                "load_state": self._load_state(identity),
                "pl_status": identity["status"],
                "native_status": identity["native_status"],
            },
            "service": service,
        }
        encoded = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()
        if len(encoded) > proto.MAX_PAYLOAD:
            raise RuntimeError("health payload exceeds UDP MTU")
        return encoded


def serve(bind, port, timeout_ms, queue_depth, result_depth, result_ttl,
          interface, node_id):
    hardware = Hardware()
    node = Node(hardware, timeout_ms, queue_depth, result_depth, result_ttl,
                interface, node_id)
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
            try:
                if msg.msg_type == proto.DISCOVER:
                    response = proto.reply(msg, proto.CAPS, payload=node.status_payload())
                elif msg.msg_type == proto.BEGIN:
                    code = node.begin(msg)
                    response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR, code=code)
                elif msg.msg_type == proto.DATA:
                    code = node.data(msg)
                    response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR,
                                           code=code, offset=msg.offset, total_len=msg.total_len)
                elif msg.msg_type == proto.COMMIT:
                    code = node.commit(msg)
                    response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR, code=code)
                elif msg.msg_type == proto.STATUS:
                    payload = node.status_payload(msg)
                    response = proto.reply(msg, proto.STATUS_REPLY if payload else proto.ERROR,
                                           payload=payload or b"",
                                           code=proto.OK if payload else proto.ERR_SESSION)
                elif msg.msg_type == proto.RESULT:
                    code, payload, total = node.result_fragment(msg)
                    response = proto.reply(msg, proto.RESULT_REPLY if code == 0 else proto.ERROR,
                                           code=code, payload=payload, offset=msg.offset,
                                           total_len=total)
                elif msg.msg_type == proto.RESULT_ACK:
                    code = node.release_result(msg)
                    response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR, code=code)
                elif msg.msg_type == proto.CANCEL:
                    code = node.cancel(msg)
                    response = proto.reply(msg, proto.ACK if code == 0 else proto.ERROR, code=code)
                elif msg.msg_type == proto.HEARTBEAT:
                    response = proto.reply(msg, proto.HEARTBEAT_REPLY,
                                           payload=node.heartbeat_payload())
                elif msg.msg_type == proto.HEALTH:
                    response = proto.reply(msg, proto.HEALTH_REPLY,
                                           payload=node.health_payload())
                else:
                    response = proto.reply(msg, proto.ERROR, code=proto.ERR_HEADER)
            except Exception:
                logging.exception("request handling failed type=%d peer=%s", msg.msg_type, peer)
                response = proto.reply(msg, proto.ERROR, code=proto.ERR_HARDWARE)
            sock.sendto(response.encode(), peer)
    finally:
        node.close()
        sock.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=42000)
    parser.add_argument("--timeout-ms", type=int, default=30000)
    parser.add_argument("--queue-depth", type=int, default=8)
    parser.add_argument("--result-depth", type=int, default=16)
    parser.add_argument("--result-ttl", type=int, default=600)
    parser.add_argument("--interface", default="eth0")
    parser.add_argument("--node-id", default="ax7020-1")
    parser.add_argument("--log-level", default="INFO")
    args = parser.parse_args()
    logging.basicConfig(level=getattr(logging, args.log_level.upper()),
                        format="%(asctime)s %(levelname)s %(message)s")
    serve(args.bind, args.port, args.timeout_ms, args.queue_depth,
          args.result_depth, args.result_ttl, args.interface, args.node_id)


if __name__ == "__main__":
    main()
