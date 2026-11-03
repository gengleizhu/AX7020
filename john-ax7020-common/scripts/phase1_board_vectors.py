#!/usr/bin/env python3
"""Generate and verify deterministic common-ABI board vectors for all algorithms."""

from __future__ import annotations

import argparse
from collections import Counter
import importlib.util
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[2]
COMMON = ROOT / "john-ax7020-common"


def load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


protocol = load("phase1_axi_protocol", COMMON / "software" / "axi_protocol.py")


def identity(algorithm: int):
    return dict(
        algorithm=algorithm,
        task=0x5048415345310000 | algorithm,
        shard=0x1102,
        batch=0x11020000 | algorithm,
        last_batch=True,
    )


def bcrypt_case():
    source = ROOT / "john-ax7020-bcrypt8" / "sim" / "integration" / "cost4"
    native = (source / "input.bin").read_bytes()
    expected = [bytes.fromhex(value) for value in json.loads((source / "expected.json").read_text())]
    batch = protocol.Batch(valid_count=32, physical_count=32, payload=native, **identity(1))

    def verify(payload):
        actual = [payload[offset:offset + 48] for offset in range(0, len(payload), 48)]
        if Counter(actual) != Counter(expected):
            raise AssertionError("bcrypt packet result set differs from the RTL reference")
        return {"records": len(actual), "cost": 4}

    return batch, verify


def descrypt_case():
    host = ROOT / "john-ax7020-descrypt8" / "host"
    sys.path.insert(0, str(host))
    codec8 = load("phase1_des_codec8", host / "codec8.py")
    vectors = json.loads((ROOT / "john-ax7020-descrypt8" / "sim" / "vectors.json").read_text())[:8]
    groups = [entry[0] for entry in vectors]
    targets = [entry[1] for entry in vectors]
    expected_masks = [entry[2] for entry in vectors]
    batch_id = identity(2)["batch"]
    native = codec8.encode_superbatch(groups, targets, batch_id)
    batch = protocol.Batch(valid_count=128, physical_count=128, payload=native, **identity(2))

    def verify(payload):
        result = codec8.decode_superresult(payload, batch_id)
        masks = [core["provisional_mask"] for core in result["cores"]]
        if masks != expected_masks:
            raise AssertionError(f"descrypt provisional masks {masks} != {expected_masks}")
        return {"cores": 8, "candidates": 128, "masks": masks}

    return batch, verify


def sha_case(algorithm: int):
    project = "john-ax7020-sha256crypt8" if algorithm == 4 else "john-ax7020-sha512crypt4"
    codec = load(f"phase1_sha{algorithm}_codec", ROOT / project / "host" / "codec.py")
    count = 96 if algorithm == 4 else 64
    max_length = 32 if algorithm == 4 else 64
    jobs = []
    for index in range(count):
        length = index % (max_length + 1)
        password = bytes(33 + ((index + offset) % 90) for offset in range(length))
        salt = f"s{index:07d}".encode()
        jobs.append((password, salt, 0x1102000000000000 | (algorithm << 12) | index, 1000))
    batch_id = identity(algorithm)["batch"]
    native = codec.encode_batch(jobs, batch_id)
    batch = protocol.Batch(valid_count=count, physical_count=count, payload=native, **identity(algorithm))

    def verify(payload):
        units = codec.decode_result(payload, batch_id)
        actual = {job_id: digest for unit in units for job_id, digest in unit["records"]}
        expected = {job_id: codec.digest(password, salt, rounds) for password, salt, job_id, rounds in jobs}
        failures = [job_id for job_id, digest in expected.items() if actual.get(job_id) != digest]
        if failures or len(actual) != count:
            raise AssertionError(f"SHA crypt mismatch count={len(failures)} records={len(actual)}")
        return {"records": len(actual), "rounds": 1000, "unit_cycles": [unit["cycles"] for unit in units]}

    return batch, verify


def case(algorithm: int):
    if algorithm == 1:
        return bcrypt_case()
    if algorithm == 2:
        return descrypt_case()
    if algorithm in (4, 5):
        return sha_case(algorithm)
    raise ValueError("algorithm must be 1, 2, 4 or 5")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("generate", "verify"))
    parser.add_argument("algorithm", type=int, choices=(1, 2, 4, 5))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    batch, verify = case(args.algorithm)
    args.directory.mkdir(parents=True, exist_ok=True)
    request = args.directory / "request.bin"
    response = args.directory / "response.bin"
    report = args.directory / "verification.json"
    if args.action == "generate":
        request.write_bytes(batch.request())
        print(f"algorithm={args.algorithm} request_bytes={request.stat().st_size} response_bytes={64 + batch.output_bytes}")
        return
    payload = batch.parse_response(response.read_bytes())
    details = verify(payload)
    result = {"pass": True, "algorithm": args.algorithm, **details}
    report.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
