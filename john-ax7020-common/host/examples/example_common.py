#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

HOST_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST_DIR))
from john_fpga_client import JohnFpgaClient, prepare_batch  # noqa: E402


def parser(description):
    result = argparse.ArgumentParser(description=description)
    result.add_argument("--host", default="169.254.173.138")
    result.add_argument("--port", type=int, default=42000)
    result.add_argument("--management-port", type=int, default=42001)
    result.add_argument("--management-key", type=Path,
                        help="enables authenticated automatic Bitstream switching")
    return result


def run(args, algorithm, candidates, target):
    prepared = prepare_batch(algorithm, candidates, target=target)
    with JohnFpgaClient(
        args.host, args.port, management_port=args.management_port,
        management_key=args.management_key,
    ) as client:
        result = client.execute(
            prepared, auto_switch=args.management_key is not None)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    if not result["matches"]:
        raise SystemExit("FPGA completed but the known candidate did not match")
