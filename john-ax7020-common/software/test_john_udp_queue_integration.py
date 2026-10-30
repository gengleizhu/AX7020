#!/usr/bin/env python3
"""Submit several real board tasks concurrently and verify result caching."""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import threading


ROOT = Path(__file__).resolve().parents[1]
CLIENT_PATH = ROOT / "host" / "john_udp_client.py"
SPEC = importlib.util.spec_from_file_location("john_udp_client", CLIENT_PATH)
client_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(client_module)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--host", default="169.254.173.138")
    parser.add_argument("--count", type=int, default=4)
    args = parser.parse_args()
    request = args.request.read_bytes()
    clients = [
        client_module.Client(args.host, 42000, 0.5, 5)
        for _ in range(args.count)
    ]
    handles = [None] * args.count
    errors = []

    def submit(index):
        try:
            handles[index] = clients[index].submit(request)
        except Exception as exc:
            errors.append((index, exc))

    threads = [threading.Thread(target=submit, args=(index,))
               for index in range(args.count)]
    try:
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        if errors:
            raise RuntimeError(f"concurrent submit failed: {errors}")

        probe = client_module.Client(args.host, 42000, 0.5, 5)
        try:
            heartbeat = client_module.parse_heartbeat(probe.heartbeat().payload)
            print({"after_submit": heartbeat})
        finally:
            probe.close()

        args.output_dir.mkdir(parents=True, exist_ok=True)
        for index, (client, handle) in enumerate(zip(clients, handles)):
            status = client.wait(handle, 0.001)
            result = client.fetch(handle)
            (args.output_dir / f"result_{index}.bin").write_bytes(result)
            client.release(handle)
            print({"index": index, "bytes": len(result), "status": status})
    finally:
        for client in clients:
            client.close()


if __name__ == "__main__":
    main()
