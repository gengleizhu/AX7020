#!/usr/bin/env python3
"""High-level host SDK for the five AX7020 John FPGA algorithms.

Callers provide candidates and a crypt target (or salt).  This module owns
padding, native packet construction, common DMA framing and result decoding.
"""

from __future__ import annotations

from dataclasses import dataclass
import importlib.util
from pathlib import Path
import random
import re
import struct
import sys
from typing import Any, Callable, Dict, Iterable, List, Optional, Union

THIS_DIR = Path(__file__).resolve().parent
ROOT = THIS_DIR.parents[1]
COMMON = ROOT / "john-ax7020-common"
sys.path.insert(0, str(THIS_DIR))
from john_udp_client import Client, ManagementClient  # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load %s" % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = _load("john_highlevel_axi_protocol", COMMON / "software" / "axi_protocol.py")
bcrypt_codec = _load("john_highlevel_bcrypt_codec", ROOT / "john-ax7020-bcrypt8" / "host" / "john_packet_codec.py")
md5_codec = _load("john_highlevel_md5_codec", ROOT / "john-ax7020-md5crypt8" / "host" / "codec.py")
sha256_codec = _load("john_highlevel_sha256_codec", ROOT / "john-ax7020-sha256crypt8" / "host" / "codec.py")
sha512_codec = _load("john_highlevel_sha512_codec", ROOT / "john-ax7020-sha512crypt4" / "host" / "codec.py")

_des_host = ROOT / "john-ax7020-descrypt8" / "host"
des_codec = _load("john_highlevel_des_codec", _des_host / "codec.py")
_prior_codec = sys.modules.get("codec")
sys.modules["codec"] = des_codec
try:
    des_codec8 = _load("john_highlevel_des_codec8", _des_host / "codec8.py")
finally:
    if _prior_codec is None:
        del sys.modules["codec"]
    else:
        sys.modules["codec"] = _prior_codec


ALGORITHMS = {
    1: "bcrypt8", 2: "descrypt8", 3: "md5crypt8",
    4: "sha256crypt8", 5: "sha512crypt4",
}
ALGORITHM_IDS = {name: number for number, name in ALGORITHMS.items()}
ALGORITHM_IDS.update({name.rstrip("84"): number for number, name in ALGORITHMS.items()})
_BCRYPT64 = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"


def algorithm_id(value: Union[int, str]) -> int:
    if isinstance(value, int) and value in ALGORITHMS:
        return value
    if isinstance(value, str):
        key = value.lower().replace("-", "").replace("_", "")
        aliases = {
            "bcrypt": 1, "bcrypt8": 1, "descrypt": 2, "descrypt8": 2,
            "md5crypt": 3, "md5crypt8": 3, "sha256crypt": 4,
            "sha256crypt8": 4, "sha512crypt": 5, "sha512crypt4": 5,
        }
        if key in aliases:
            return aliases[key]
    raise ValueError("unknown algorithm %r" % (value,))


def _as_bytes(value: Union[str, bytes], field: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError("%s must be str or bytes" % field)


def _bcrypt_decode64(text: str, count: int) -> bytes:
    if any(char not in _BCRYPT64 for char in text):
        raise ValueError("invalid bcrypt base64")
    bits = "".join(format(_BCRYPT64.index(char), "06b") for char in text)
    if len(bits) < count * 8:
        raise ValueError("truncated bcrypt base64")
    return bytes(int(bits[index:index + 8], 2) for index in range(0, count * 8, 8))


def _bcrypt_target(target: str):
    match = re.fullmatch(r"\$2([abxy])\$(\d\d)\$([./A-Za-z0-9]{53})", target)
    if not match:
        raise ValueError("expected a canonical 60-character bcrypt target")
    subtype, cost_text, body = match.groups()
    cost = int(cost_text)
    if not 4 <= cost <= 31:
        raise ValueError("bcrypt cost must be 4..31")
    return subtype, cost, _bcrypt_decode64(body[:22], 16), _bcrypt_decode64(body[22:], 23)


def _parse_md5_target(target: str):
    match = re.fullmatch(r"\$1\$([./0-9A-Za-z]{1,8})\$([./0-9A-Za-z]{22})", target)
    if not match:
        raise ValueError("invalid MD5-crypt target")
    return match.group(1).encode("ascii"), 1000


def _parse_sha_target(target: str, prefix: str):
    parts = target.split("$")
    if len(parts) == 4 and parts[:2] == ["", prefix]:
        rounds, salt, checksum = 5000, parts[2], parts[3]
    elif len(parts) == 5 and parts[:2] == ["", prefix] and parts[2].startswith("rounds="):
        rounds, salt, checksum = int(parts[2][7:]), parts[3], parts[4]
    else:
        raise ValueError("invalid SHA-crypt target")
    expected_length = 43 if prefix == "5" else 86
    if not 1000 <= rounds <= 999_999_999 or not 1 <= len(salt) <= 16:
        raise ValueError("SHA-crypt rounds/salt out of hardware range")
    if len(checksum) != expected_length or any(c not in "./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz" for c in checksum):
        raise ValueError("invalid SHA-crypt checksum")
    return salt.encode("ascii"), rounds


@dataclass
class PreparedBatch:
    algorithm: int
    batch: Any
    candidates: List[bytes]
    target: Optional[str]
    _decode_payload: Callable[[bytes], List[Dict[str, Any]]]

    def request(self) -> bytes:
        return self.batch.request()

    def decode_response(self, response: bytes) -> List[Dict[str, Any]]:
        return self._decode_payload(self.batch.parse_response(response))


def _identity(task_id, shard_id, batch_id):
    return (
        random.getrandbits(64) if task_id is None else task_id,
        shard_id,
        random.getrandbits(32) if batch_id is None else batch_id,
    )


def _prepare_bcrypt(candidates, target, task_id, shard_id, batch_id, last_batch):
    if target is None:
        raise ValueError("bcrypt requires a full target hash")
    words = [_as_bytes(item, "candidate") for item in candidates]
    if not 1 <= len(words) <= 170:
        raise ValueError("bcrypt accepts 1..170 candidates per batch")
    for word in words:
        if len(word) > 72 or b"\0" in word:
            raise ValueError("bcrypt candidates must be 0..72 bytes without NUL")
    subtype, cost, salt, expected = _bcrypt_target(target)
    task, shard, tag = _identity(task_id, shard_id, batch_id)
    packet_id = tag & 0xFFFF
    config = (struct.pack("<4I", *struct.unpack(">4I", salt)) + subtype.encode("ascii") +
              struct.pack("<I", 1 << cost) + b"\0\0\xcc")
    word_payload = b"".join(word + (b"\0" if len(word) < 72 else b"") for word in words)
    native = b"".join(packet.encode() for packet in (
        bcrypt_codec.Packet(3, 0, config),
        bcrypt_codec.Packet(2, packet_id, b"\0" * 5 + b"\xbb"),
        bcrypt_codec.Packet(1, packet_id, word_payload),
    ))
    batch = protocol.Batch(1, task, shard, tag, len(words), len(words), native, last_batch)

    def decode(payload):
        packets = bcrypt_codec.Decoder().feed(payload)
        if len(packets) != len(words):
            raise ValueError("bcrypt result count mismatch")
        records = [None] * len(words)
        for packet in packets:
            if packet.type != 0xD3 or packet.id != packet_id or len(packet.payload) != 30:
                raise ValueError("invalid bcrypt result packet")
            word_id, generation = struct.unpack_from("<HI", packet.payload)
            if generation != 0 or word_id >= len(words) or records[word_id] is not None:
                raise ValueError("invalid/duplicate bcrypt result identity")
            raw = struct.pack(">6I", *struct.unpack("<6I", packet.payload[6:]))
            records[word_id] = {
                "index": word_id, "candidate": words[word_id].decode("utf-8", "replace"),
                "candidate_hex": words[word_id].hex(), "digest_hex": raw.hex(),
                "matched": raw[:23] == expected,
            }
        return records

    return PreparedBatch(1, batch, words, target, decode)


def _prepare_des(candidates, target, task_id, shard_id, batch_id, last_batch):
    if target is None:
        raise ValueError("DES-crypt requires a full 13-character target")
    words = [_as_bytes(item, "candidate").decode("ascii") for item in candidates]
    if not 1 <= len(words) <= 128:
        raise ValueError("DES-crypt accepts 1..128 candidates per batch")
    padded = words + [""] * (128 - len(words))
    groups = [padded[offset:offset + 16] for offset in range(0, 128, 16)]
    targets = [target] * 8
    task, shard, tag = _identity(task_id, shard_id, batch_id)
    native = des_codec8.encode_superbatch(groups, targets, tag)
    batch = protocol.Batch(2, task, shard, tag, len(words), 128, native, last_batch)

    def decode(payload):
        result = des_codec8.decode_superresult(payload, tag)
        records = []
        for core_index, core in enumerate(result["cores"]):
            verified = des_codec.verify_matches(groups[core_index], target, core["provisional_mask"])
            for local_index in range(16):
                index = core_index * 16 + local_index
                if index < len(words):
                    records.append({
                        "index": index, "candidate": words[index],
                        "candidate_hex": words[index].encode("ascii").hex(),
                        "provisional": bool(core["provisional_mask"] & (1 << local_index)),
                        "matched": local_index in verified,
                    })
        return records

    return PreparedBatch(2, batch, [word.encode("ascii") for word in words], target, decode)


def _prepare_digest(algorithm, candidates, target, salt, rounds, task_id, shard_id,
                    batch_id, last_batch):
    codec, capacity = {
        3: (md5_codec, 96), 4: (sha256_codec, 96), 5: (sha512_codec, 64),
    }[algorithm]
    words = [_as_bytes(item, "candidate") for item in candidates]
    if not 1 <= len(words) <= capacity:
        raise ValueError("%s accepts 1..%d candidates per batch" % (ALGORITHMS[algorithm], capacity))
    if target:
        parsed_salt, parsed_rounds = (_parse_md5_target(target) if algorithm == 3 else
                                      _parse_sha_target(target, "5" if algorithm == 4 else "6"))
        if salt is not None and _as_bytes(salt, "salt") != parsed_salt:
            raise ValueError("explicit salt differs from target")
        if rounds is not None and rounds != parsed_rounds:
            raise ValueError("explicit rounds differs from target")
        salt, rounds = parsed_salt, parsed_rounds
    else:
        if salt is None:
            raise ValueError("salt or full target is required")
        salt = _as_bytes(salt, "salt")
        rounds = 1000 if algorithm == 3 else (5000 if rounds is None else rounds)
    padded = words + [b""] * (capacity - len(words))
    task, shard, tag = _identity(task_id, shard_id, batch_id)
    if algorithm == 3:
        jobs = [(word, salt, index + 1) for index, word in enumerate(padded)]
    else:
        jobs = [(word, salt, index + 1, rounds) for index, word in enumerate(padded)]
    native = codec.encode_batch(jobs, tag)
    batch = protocol.Batch(algorithm, task, shard, tag, len(words), capacity, native, last_batch)

    def decode(payload):
        units = codec.decode_result(payload, tag)
        raw_by_id = {job_id: raw for unit in units for job_id, raw in unit["records"]}
        if len(raw_by_id) != capacity:
            raise ValueError("native result count mismatch")
        records = []
        for index, word in enumerate(words):
            raw = raw_by_id[index + 1]
            if algorithm == 3:
                crypt = "$1$" + salt.decode("ascii") + "$" + codec.crypt_checksum(raw)
            else:
                prefix = "$5$" if algorithm == 4 else "$6$"
                rounds_prefix = "" if rounds == 5000 else "rounds=%d$" % rounds
                crypt = prefix + rounds_prefix + salt.decode("ascii") + "$" + codec.crypt_checksum(raw)
            records.append({
                "index": index, "candidate": word.decode("utf-8", "replace"),
                "candidate_hex": word.hex(), "digest_hex": raw.hex(),
                "crypt": crypt, "matched": target is not None and crypt == target,
            })
        return records

    return PreparedBatch(algorithm, batch, words, target, decode)


def prepare_batch(algorithm: Union[int, str], candidates: Iterable[Union[str, bytes]], *,
                  target: Optional[str] = None, salt: Optional[Union[str, bytes]] = None,
                  rounds: Optional[int] = None, task_id: Optional[int] = None,
                  shard_id: int = 0, batch_id: Optional[int] = None,
                  last_batch: bool = True) -> PreparedBatch:
    """Create one hardware batch using the same call shape for all algorithms."""
    number = algorithm_id(algorithm)
    items = list(candidates)
    if number == 1:
        return _prepare_bcrypt(items, target, task_id, shard_id, batch_id, last_batch)
    if number == 2:
        return _prepare_des(items, target, task_id, shard_id, batch_id, last_batch)
    return _prepare_digest(number, items, target, salt, rounds, task_id, shard_id,
                           batch_id, last_batch)


class JohnFpgaClient:
    """One public client for status, task execution and optional FPGA switching."""

    def __init__(self, host: str, port: int = 42000, timeout: float = 0.5,
                 retries: int = 5, management_port: int = 42001,
                 management_key: Optional[Union[str, bytes, Path]] = None):
        self.transport = Client(host, port, timeout, retries)
        self.management = (ManagementClient(host, management_port, management_key,
                                            timeout=max(timeout, 1.0), retries=retries)
                           if management_key is not None else None)

    def close(self):
        self.transport.close()
        if self.management is not None:
            self.management.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        self.close()

    def capabilities(self):
        from john_udp_client import parse_status
        return parse_status(self.transport.discover().payload)

    def heartbeat(self):
        from john_udp_client import parse_heartbeat
        return parse_heartbeat(self.transport.heartbeat().payload)

    def health(self):
        import json
        return json.loads(self.transport.health().payload)

    def switch_algorithm(self, algorithm: Union[int, str], *, recover: bool = False,
                         drain_seconds: float = 60, wait: bool = True):
        if self.management is None:
            raise RuntimeError("management_key is required for remote switching")
        return self.management.switch_algorithm(
            algorithm_id(algorithm), recover=recover,
            drain_seconds=drain_seconds, wait=wait,
        )

    def execute(self, prepared: PreparedBatch, *, poll_interval: float = 0.01,
                auto_switch: bool = False):
        current = self.capabilities()["algorithm"]
        if current != prepared.algorithm:
            if not auto_switch:
                raise RuntimeError("loaded algorithm %d, task requires %d" %
                                   (current, prepared.algorithm))
            self.switch_algorithm(prepared.algorithm)
            current = self.capabilities()["algorithm"]
            if current != prepared.algorithm:
                raise RuntimeError("algorithm switch self-check failed")
        response, status = self.transport.run(prepared.request(), poll_interval)
        records = prepared.decode_response(response)
        return {
            "algorithm": prepared.algorithm,
            "algorithm_name": ALGORITHMS[prepared.algorithm],
            "task_id": prepared.batch.task,
            "shard_id": prepared.batch.shard,
            "batch_id": prepared.batch.batch,
            "status": status,
            "records": records,
            "matches": [record for record in records if record.get("matched")],
        }
