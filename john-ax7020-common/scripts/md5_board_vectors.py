#!/usr/bin/env python3
"""Generate and verify a deterministic MD5-crypt common-ABI board batch."""

from __future__ import annotations

import argparse
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


codec = load("board_md5_codec", ROOT / "john-ax7020-md5crypt8" / "host" / "codec.py")
protocol = load("board_md5_protocol", COMMON / "software" / "axi_protocol.py")

TRANSACTION_ID = 0x1030
TASK_ID = 0x4D44354352595054
SHARD_ID = 0x1030


def jobs():
    alphabet = b"0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz./"
    return [
        (
            bytes(alphabet[(index + offset) % len(alphabet)]
                  for offset in range(index % 65)),
            f"s{index:07d}".encode("ascii"),
            0x0000000100000000 + index,
        )
        for index in range(96)
    ]


def batch():
    test_jobs = jobs()
    native = codec.encode_batch(test_jobs, TRANSACTION_ID)
    return test_jobs, protocol.Batch(
        algorithm=3,
        task=TASK_ID,
        shard=SHARD_ID,
        batch=TRANSACTION_ID,
        valid_count=96,
        physical_count=96,
        payload=native,
        last_batch=True,
    )


def generate(directory: Path):
    test_jobs, test_batch = batch()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / "request.bin").write_bytes(test_batch.request())
    expected = {
        "algorithm": 3,
        "transaction_id": TRANSACTION_ID,
        "records": [
            {"job_id": job_id, "digest_hex": codec.digest(password, salt).hex()}
            for password, salt, job_id in test_jobs
        ],
    }
    (directory / "expected.json").write_text(
        json.dumps(expected, indent=2), encoding="utf-8"
    )
    print("algorithm=3 request_bytes=%d response_bytes=%d" %
          ((directory / "request.bin").stat().st_size,
           64 + test_batch.output_bytes))


def verify(directory: Path):
    test_jobs, test_batch = batch()
    payload = test_batch.parse_response((directory / "response.bin").read_bytes())
    units = codec.decode_result(payload, TRANSACTION_ID)
    actual = {
        job_id: digest
        for unit in units
        for job_id, digest in unit["records"]
    }
    failures = [
        job_id for password, salt, job_id in test_jobs
        if actual.get(job_id) != codec.digest(password, salt)
    ]
    result = {
        "pass": not failures and len(actual) == 96,
        "algorithm": 3,
        "records": len(actual),
        "unit_cycles": [unit["cycles"] for unit in units],
        "failures": failures,
    }
    (directory / "verification.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result, indent=2))
    if not result["pass"]:
        raise SystemExit(1)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("generate", "verify"))
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    if args.action == "generate":
        generate(args.directory)
    else:
        verify(args.directory)


if __name__ == "__main__":
    main()
