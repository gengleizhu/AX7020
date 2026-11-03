#!/usr/bin/env python3
"""Local root-only full-bitstream transition; fail closed after shutdown.

Requires a node service implementing the maintenance health field. Firmware
must already be installed under /lib/firmware and verified by a deployment
manifest. Does not download firmware or expose a remote programming endpoint.
"""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path
import socket
import struct
import subprocess
import time

import john_udp_protocol as proto

MAINTENANCE = Path('/run/john-node.maintenance')
DMA = Path('/sys/bus/platform/drivers/xilinx-vdma')
MANAGER = Path('/sys/class/fpga_manager/fpga0')


def run(*args):
    subprocess.run(args, check=True, timeout=30)


def health(port):
    sequence = int.from_bytes(os.urandom(4), 'big')
    request = proto.Message(proto.HEALTH, sequence=sequence)
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.settimeout(2)
        sock.connect(('127.0.0.1', port))
        sock.send(request.encode())
        reply = proto.decode(sock.recv(proto.MAX_DATAGRAM + 1))
    if reply.msg_type != proto.HEALTH_REPLY or reply.sequence != sequence:
        raise RuntimeError('invalid local health response')
    return json.loads(reply.payload)


def validate_manifest(path):
    manifest = json.loads(path.read_text())
    name = manifest['firmware']
    if not isinstance(name, str) or Path(name).name != name or not name.endswith('.bin'):
        raise ValueError('firmware must be a plain .bin filename')
    if manifest['algorithm'] not in range(1, 6):
        raise ValueError('unsupported algorithm')
    data = (Path('/lib/firmware') / name).read_bytes()
    if hashlib.sha256(data).hexdigest() != manifest['sha256'].lower():
        raise ValueError('firmware SHA256 mismatch')
    if manifest['register_abi'] != 0x10001 or manifest['stream_abi'] != 0x10000:
        raise ValueError('unsupported ABI')
    return manifest


def identify(manifest):
    # Only access PL after FPGA Manager reports successful configuration.
    def read(offset):
        return int(subprocess.check_output(
            ['devmem', hex(0x43c00000 + offset), '32'], timeout=3).strip(), 16)
    expected = {0: 0x4a435250, 4: manifest['register_abi'],
                12: manifest['stream_abi'], 32: manifest['algorithm']}
    for offset, value in expected.items():
        if read(offset) != value:
            raise RuntimeError('identity mismatch at offset %#x' % offset)
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        status = read(0x84)
        if status & 1 and not status & 0x2e:
            return status
        time.sleep(.02)
    raise RuntimeError('PL initialization timeout')


def switch(manifest, port, drain_seconds):
    if MAINTENANCE.exists():
        raise RuntimeError('maintenance already active; inspect prior failure before recovery')
    stopped = False
    MAINTENANCE.write_text('draining\n')
    try:
        deadline = time.monotonic() + drain_seconds
        while True:
            info = health(port)
            service = info['service']
            if service.get('maintenance') is not True:
                raise RuntimeError('node does not acknowledge maintenance mode')
            if service['tasks_tracked'] == 0 and not info['dma']['running']:
                break
            if time.monotonic() >= deadline:
                raise RuntimeError('drain timeout: tasks/results remain; no firmware loaded')
            time.sleep(.2)
        stopped = True
        run('/etc/init.d/john-node', 'stop')
        # rmmod must succeed: it proves the userspace DMA descriptor is closed.
        run('rmmod', 'john_dma')
        (DMA / 'unbind').write_text('40400000.dma')
        MAINTENANCE.write_text('loading\n')
        (MANAGER / 'flags').write_text('0')
        (MANAGER / 'firmware').write_text(manifest['firmware'])
        if (MANAGER / 'state').read_text().strip() != 'operating':
            raise RuntimeError('FPGA manager did not reach operating state')
        status = identify(manifest)
        (DMA / 'bind').write_text('40400000.dma')
        run('modprobe', 'john_dma')
        run('/etc/init.d/john-node', 'start')
        deadline = time.monotonic() + 5
        while True:
            try:
                loaded = health(port)
                if loaded['bitstream']['algorithm'] != manifest['algorithm']:
                    raise RuntimeError('service algorithm mismatch')
                break
            except (OSError, RuntimeError):
                if time.monotonic() >= deadline:
                    raise
                time.sleep(.2)
        MAINTENANCE.unlink()
        print(json.dumps({'loaded': manifest['algorithm'], 'pl_status': status}))
    except Exception:
        if not stopped:
            MAINTENANCE.unlink()
        # After shutdown leave admission blocked and do not touch unknown PL.
        raise


def recover(manifest, port):
    """Explicit recovery from failed shutdown/load; never bypass normal drain."""
    if not MAINTENANCE.exists():
        raise RuntimeError('recovery requires an existing failed maintenance transition')
    run('/etc/init.d/john-node', 'stop')
    if Path('/sys/module/john_dma').exists():
        run('rmmod', 'john_dma')
    if (DMA / '40400000.dma').exists():
        (DMA / 'unbind').write_text('40400000.dma')
    MAINTENANCE.write_text('recovering\n')
    (MANAGER / 'flags').write_text('0')
    (MANAGER / 'firmware').write_text(manifest['firmware'])
    if (MANAGER / 'state').read_text().strip() != 'operating':
        raise RuntimeError('recovery configuration failed')
    status = identify(manifest)
    (DMA / 'bind').write_text('40400000.dma')
    run('modprobe', 'john_dma')
    run('/etc/init.d/john-node', 'start')
    deadline = time.monotonic() + 5
    while True:
        try:
            info = health(port)
            if info['bitstream']['algorithm'] != manifest['algorithm']:
                raise RuntimeError('recovery service algorithm mismatch')
            break
        except (OSError, RuntimeError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(.2)
    MAINTENANCE.unlink()
    print(json.dumps({'recovered': manifest['algorithm'], 'pl_status': status}))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('manifest', type=Path)
    parser.add_argument('--port', type=int, default=42000)
    parser.add_argument('--drain-seconds', type=float, default=60)
    parser.add_argument('--check-only', action='store_true')
    parser.add_argument('--recover', action='store_true')
    args = parser.parse_args()
    if os.geteuid() != 0:
        raise SystemExit('root required')
    with open('/run/john-bitstream.lock', 'w') as lock:
        libc = ctypes.CDLL(None, use_errno=True)
        libc.flock.argtypes = [ctypes.c_int, ctypes.c_int]
        libc.flock.restype = ctypes.c_int
        if libc.flock(lock.fileno(), 2 | 4):  # Linux LOCK_EX | LOCK_NB
            raise OSError(ctypes.get_errno(), 'bitstream transition lock unavailable')
        manifest = validate_manifest(args.manifest)
        if args.check_only:
            print(json.dumps(manifest))
        elif args.recover:
            recover(manifest, args.port)
        else:
            switch(manifest, args.port, args.drain_seconds)


if __name__ == '__main__':
    main()
