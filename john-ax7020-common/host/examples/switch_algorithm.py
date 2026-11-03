#!/usr/bin/env python3
import argparse
import json
from pathlib import Path
import sys

HOST_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HOST_DIR))
from john_fpga_client import JohnFpgaClient  # noqa: E402

parser = argparse.ArgumentParser(description="Authenticated remote FPGA algorithm switch")
parser.add_argument("algorithm", choices=("bcrypt", "descrypt", "md5crypt", "sha256crypt", "sha512crypt"))
parser.add_argument("--host", default="169.254.173.138")
parser.add_argument("--key", type=Path, required=True)
parser.add_argument("--recover", action="store_true",
                    help="explicitly recover a prior failed maintenance transition")
args = parser.parse_args()

with JohnFpgaClient(args.host, management_key=args.key) as client:
    result = client.switch_algorithm(args.algorithm, recover=args.recover)
print(json.dumps(result, indent=2))

