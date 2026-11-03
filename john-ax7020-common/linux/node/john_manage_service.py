#!/usr/bin/env python3
"""Authenticated UDP control plane for whitelisted FPGA bitstreams.

This daemon is deliberately separate from john-node so it remains available
while the data-plane service and DMA driver are restarted during a switch.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
from pathlib import Path
import random
import socket
import subprocess
import threading
import time

import john_bitstream
import john_management as auth
import john_udp_protocol as proto


class ManagementService:
    def __init__(self, key, manifest_dir, bitstream_tool, node_port):
        self.key = key
        self.manifest_dir = Path(manifest_dir)
        self.bitstream_tool = str(bitstream_tool)
        self.node_port = node_port
        self.lock = threading.Lock()
        self.operation = {
            "operation_id": "", "state": "idle", "algorithm": 0,
            "recover": False, "started_at": 0, "finished_at": 0,
            "error_code": "",
        }
        self.nonces = {}
        self.responses = {}

    def manifests(self):
        result = {}
        for path in sorted(self.manifest_dir.glob("*.json")):
            try:
                manifest = john_bitstream.validate_manifest(path)
                algorithm = manifest["algorithm"]
                if algorithm in result:
                    raise ValueError("duplicate algorithm manifest")
                result[algorithm] = (path, manifest)
            except Exception:
                logging.exception("rejecting bitstream manifest %s", path)
        return result

    def _verify(self, request, action):
        values = auth.decode(request.payload, self.key, request.session,
                             request.sequence, max_age=60)
        if values.get("action") != action:
            raise ValueError("wrong management action")
        nonce = values.get("nonce")
        if not isinstance(nonce, str) or len(nonce) < 16:
            raise PermissionError("invalid management nonce")
        now = time.monotonic()
        with self.lock:
            self.nonces = {item: expiry for item, expiry in self.nonces.items()
                           if expiry > now}
            if nonce in self.nonces:
                raise RuntimeError("replayed management request")
            self.nonces[nonce] = now + 300
        return values

    def _signed_reply(self, request, msg_type, action, values):
        body = dict(values)
        body.update({"action": action, "timestamp": int(time.time())})
        payload = auth.encode(body, self.key, request.session, request.sequence)
        return proto.reply(request, msg_type, payload=payload)

    def _snapshot(self):
        with self.lock:
            return dict(self.operation)

    def _run_switch(self, operation_id, algorithm, path, recover, drain_seconds):
        with self.lock:
            self.operation["state"] = "running"
            self.operation["started_at"] = int(time.time())
        command = [self.bitstream_tool, str(path), "--port", str(self.node_port)]
        if recover:
            command.append("--recover")
        else:
            command += ["--drain-seconds", str(drain_seconds)]
        try:
            completed = subprocess.run(
                command, check=True, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, universal_newlines=True,
                timeout=max(90.0, drain_seconds + 60.0),
            )
            logging.info("bitstream operation %s succeeded: %s", operation_id,
                         completed.stdout.strip())
            state, error = "succeeded", ""
        except Exception as exc:
            logging.exception("bitstream operation %s failed", operation_id)
            if isinstance(exc, subprocess.CalledProcessError):
                logging.error("john-bitstream stderr: %s", (exc.stderr or "").strip())
            state, error = "failed", "switch_failed"
        with self.lock:
            if self.operation["operation_id"] == operation_id:
                self.operation["state"] = state
                self.operation["error_code"] = error
                self.operation["finished_at"] = int(time.time())

    def dispatch(self, request):
        """Return the cached reply for an exact UDP retry; reject nonce reuse."""
        key = (request.session, request.sequence)
        now = time.monotonic()
        with self.lock:
            self.responses = {item: entry for item, entry in self.responses.items()
                              if entry[0] > now}
            cached = self.responses.get(key)
            if cached is not None:
                if cached[1] != request.payload:
                    raise RuntimeError("replayed management request")
                return cached[2]
        response = self._dispatch_new(request)
        with self.lock:
            self.responses[key] = (now + 300, request.payload, response)
        return response

    def _dispatch_new(self, request):
        if request.msg_type == proto.MANAGE_CAPS:
            self._verify(request, "caps")
            manifests = self.manifests()
            algorithms = [{
                "algorithm": number,
                "name": auth.ALGORITHMS[number],
                "firmware": manifest["firmware"],
                "register_abi": manifest["register_abi"],
                "stream_abi": manifest["stream_abi"],
            } for number, (_, manifest) in sorted(manifests.items())]
            try:
                loaded = john_bitstream.health(self.node_port)["bitstream"]["algorithm"]
            except Exception:
                loaded = 0
            return self._signed_reply(
                request, proto.MANAGE_CAPS_REPLY, "caps_reply",
                {"algorithms": algorithms, "loaded_algorithm": loaded,
                 "operation": self._snapshot()},
            )
        if request.msg_type == proto.MANAGE_STATUS:
            self._verify(request, "status")
            return self._signed_reply(
                request, proto.MANAGE_STATUS_REPLY, "status_reply",
                {"operation": self._snapshot()},
            )
        if request.msg_type == proto.MANAGE_SWITCH:
            values = self._verify(request, "switch")
            algorithm = values.get("algorithm")
            recover = values.get("recover", False)
            drain_seconds = values.get("drain_seconds", 60)
            if (not isinstance(algorithm, int) or not isinstance(recover, bool) or
                    not isinstance(drain_seconds, (int, float)) or
                    not 0 <= drain_seconds <= 300):
                raise ValueError("invalid switch parameters")
            manifests = self.manifests()
            if algorithm not in manifests:
                return proto.reply(request, proto.ERROR,
                                   code=proto.ERR_UNSUPPORTED_ALGORITHM)
            with self.lock:
                if self.operation["state"] in ("queued", "running"):
                    return proto.reply(request, proto.ERROR,
                                       code=proto.ERR_MANAGEMENT_BUSY)
                operation_id = "%08x%08x" % (int(time.time()), random.getrandbits(32))
                self.operation = {
                    "operation_id": operation_id, "state": "queued",
                    "algorithm": algorithm, "recover": recover,
                    "started_at": 0, "finished_at": 0, "error_code": "",
                }
            worker = threading.Thread(
                target=self._run_switch,
                args=(operation_id, algorithm, manifests[algorithm][0], recover,
                      float(drain_seconds)), daemon=True,
            )
            worker.start()
            return self._signed_reply(
                request, proto.MANAGE_SWITCH_REPLY, "switch_reply",
                {"operation": self._snapshot()},
            )
        raise ValueError("unsupported management message")


def serve(args):
    key = auth.load_key(args.key_file)
    service = ManagementService(key, args.manifest_dir, args.bitstream_tool,
                                args.node_port)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.bind((args.bind, args.port))
        logging.info("john-manage listening on %s:%d", args.bind, args.port)
        while True:
            datagram, peer = sock.recvfrom(proto.MAX_DATAGRAM + 1)
            request = None
            try:
                request = proto.decode(datagram)
                response = service.dispatch(request)
            except PermissionError:
                logging.warning("management authentication rejected peer=%s", peer)
                if request is None:
                    continue
                response = proto.reply(request, proto.ERROR, code=proto.ERR_AUTH)
            except RuntimeError as exc:
                if request is None:
                    continue
                code = proto.ERR_REPLAY if "replayed" in str(exc) else proto.ERR_REQUEST
                response = proto.reply(request, proto.ERROR, code=code)
            except Exception:
                logging.exception("management request failed peer=%s", peer)
                if request is None:
                    continue
                response = proto.reply(request, proto.ERROR, code=proto.ERR_REQUEST)
            sock.sendto(response.encode(), peer)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bind", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=42001)
    parser.add_argument("--node-port", type=int, default=42000)
    parser.add_argument("--key-file", type=Path, required=True)
    parser.add_argument("--manifest-dir", type=Path,
                        default=Path("/etc/john/bitstreams"))
    parser.add_argument("--bitstream-tool", default="/usr/sbin/john-bitstream")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)s %(message)s")
    if os.geteuid() != 0:
        raise SystemExit("root required")
    serve(args)


if __name__ == "__main__":
    main()
