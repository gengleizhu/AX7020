"""Windows UDP -> 本机仿真桥 -> XSIM真实RTL -> UDP结果。

仿真桥只接收输入流、不读取expected.json、不调用CPU bcrypt。
CPU已知答案仅由客户端在收到RTL结果以后对比。
"""
import argparse
import concurrent.futures
import hashlib
import json
from pathlib import Path
import secrets
import socket
import subprocess
import threading
import time

from john_packet_codec import Decoder
from sim_udp_transport import Assembly, Frame, DATA, COMMIT, POLL, GET, REPLY, ERROR, CHUNK

ROOT = Path(__file__).resolve().parents[1]


def run_rtl(raw, cores, out, vivado):
    decoder = Decoder()
    packets = decoder.feed(raw)
    if decoder.buffer or [p.type for p in packets] != [3, 2, 1]:
        raise ValueError("expected complete CMP_CONFIG/WORD_GEN/WORD_LIST batch")
    cfg = packets[0].payload
    if len(cfg) != 24 or cfg[16] not in b"abxy" or cfg[-3:] != b"\0\0\xcc":
        raise ValueError("invalid compare configuration")
    iterations = int.from_bytes(cfg[17:21], "little")
    if not 16 <= iterations <= (1 << 20) or iterations & (iterations-1):
        raise ValueError("invalid iteration count")
    if packets[1].payload != b"\0"*5+b"\xbb":
        raise ValueError("offline backend supports dictionary pass-through only")
    words = packets[2].payload.split(b"\0")
    if words[-1] != b"" or len(words)-1 != 32 or any(len(w)>71 for w in words[:-1]):
        raise ValueError("offline benchmark requires 32 null-terminated words <=71 bytes")
    out.mkdir(parents=True, exist_ok=False)  # 防止沿用旧结果冒充本次输出。
    (out / "received_input.bin").write_bytes(raw)
    (out / "input.mem").write_text("".join(f"{b:02x}\n" for b in raw))
    command = [vivado, "-mode", "batch", "-source", str(ROOT / "vivado/simulate_integration.tcl"),
               "-log", str(out / "vivado.log"), "-journal", str(out / "vivado.jou"),
               "-tclargs", str(cores), str(out / "input.mem"), str(len(raw)), str(out)]
    with (out / "process.log").open("w") as log:
        subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                       check=True, timeout=1800)
    result = bytes.fromhex((out / "axis_output.hex").read_text())
    decoder = Decoder()
    packets = decoder.feed(result)
    if decoder.buffer or len(packets) != 32 or any(p.type != 0xd3 for p in packets):
        raise ValueError("invalid actual RTL output")
    return result


class LocalRtlServer:
    def __init__(self, cores, out, vivado):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.bind(("127.0.0.1", 0))
        self.sock.settimeout(.2)
        self.address = self.sock.getsockname()
        self.stop = threading.Event()
        self.pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        self.cores, self.out, self.vivado = cores, out, vivado
        self.error = None

    def serve(self):
        assembly, future, owner = None, None, None
        try:
            while not self.stop.is_set():
                try:
                    raw, address = self.sock.recvfrom(1500)
                except socket.timeout:
                    continue
                try:
                    f = Frame.decode(raw)
                except ValueError:
                    continue
                key = (address, f.session, f.request)
                if owner is None:
                    if f.kind != DATA:
                        continue
                    owner, assembly = key, Assembly(f)
                if owner != key:
                    continue
                response = b""
                kind = REPLY
                try:
                    if f.kind == DATA:
                        assembly.add(f)
                        response = b"ACK"
                    elif f.kind == COMMIT:
                        missing = assembly.missing()
                        if missing:
                            response = json.dumps({"missing": missing}).encode()
                        else:
                            if future is None:
                                future = self.pool.submit(run_rtl, assembly.finish(), self.cores, self.out, self.vivado)
                            response = b"RUNNING"
                    elif f.kind in (POLL, GET):
                        if future is None or not future.done():
                            response = b"RUNNING"
                        else:
                            result = future.result()
                            if f.kind == POLL:
                                response = json.dumps({"ready": True, "bytes": len(result)}).encode()
                            else:
                                begin = f.index * CHUNK
                                response = result[begin:begin+CHUNK]
                    else:
                        raise ValueError("unexpected message")
                except Exception as exc:
                    response, kind = str(exc).encode()[:CHUNK], ERROR
                self.sock.sendto(Frame(kind, f.session, f.request, f.index, f.count,
                                       len(response), response).encode(), address)
        except Exception as exc:
            self.error = exc
        finally:
            self.sock.close()
            self.pool.shutdown(wait=True)


def client(address, raw, timeout=1800):
    session, request = secrets.randbits(64), secrets.randbits(32)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.settimeout(.5)
    # 小分片强制覆盖头和载荷的跨UDP重组；生产帧上限1200，保持低于MTU1500。
    chunks = [raw[i:i+73] for i in range(0, len(raw), 73)]
    frames = [Frame(DATA, session, request, i, len(chunks), len(raw), p) for i,p in enumerate(chunks)]
    retries = 0
    def exchange(frame):
        nonlocal retries
        for attempt in range(10):
            sock.sendto(frame.encode(), address)
            deadline = time.monotonic()+.5
            while time.monotonic()<deadline:
                try:
                    packet, peer = sock.recvfrom(1500)
                except socket.timeout:
                    break
                if peer != address:
                    continue
                try:
                    reply = Frame.decode(packet)
                except ValueError:
                    continue
                if (reply.session, reply.request, reply.index) != (session, request, frame.index):
                    continue
                if reply.kind == ERROR:
                    raise RuntimeError(reply.payload.decode())
                return reply.payload
            retries += 1
        raise TimeoutError("UDP reply timeout")
    started = time.monotonic()
    try:
        # 明确注入乱序、重复和一片缺失，COMMIT必须要求重传，不能启动不完整任务。
        for i in reversed(range(len(frames))):
            if i != 2:
                exchange(frames[i])
        exchange(frames[0])
        reply = json.loads(exchange(Frame(COMMIT,session,request)))
        if reply != {"missing": [2]}:
            raise AssertionError(f"missing fragment not detected: {reply}")
        exchange(frames[2])
        assert exchange(Frame(COMMIT,session,request)) == b"RUNNING"
        assert exchange(Frame(COMMIT,session,request)) == b"RUNNING"  # 幂等启动
        while True:
            if time.monotonic()-started > timeout:
                raise TimeoutError("RTL backend timeout")
            reply = exchange(Frame(POLL,session,request))
            if reply != b"RUNNING":
                info = json.loads(reply)
                break
            time.sleep(.2)
        count = (info["bytes"]+CHUNK-1)//CHUNK
        result = b"".join(exchange(Frame(GET,session,request,i,count)) for i in range(count))
        if len(result) != info["bytes"]:
            raise AssertionError("result length")
        return result, {"session": session, "request": request, "injected_missing": 1,
                        "injected_duplicate": 1, "out_of_order": True, "timeout_retries": retries,
                        "wall_seconds_including_vivado": time.monotonic()-started}
    finally:
        sock.close()


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--cores", type=int, choices=(1,8), default=8)
    p.add_argument("--cost", type=int, choices=(4,5), default=4)
    p.add_argument("--vivado", default=r"C:\Xilinx\Vivado\2018.3\bin\vivado.bat")
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    out = args.output.resolve()
    source = ROOT / f"sim/integration/cost{args.cost}"
    raw = (source / "input.bin").read_bytes()
    server = LocalRtlServer(args.cores, out, args.vivado)
    thread = threading.Thread(target=server.serve)
    thread.start()
    try:
        print(f"UDP_RTL_START cores={args.cores} cost={args.cost} backend=XSIM address={server.address}", flush=True)
        actual, audit = client(server.address, raw)
        expected = json.loads((source / "expected.json").read_text())
        decoder = Decoder()
        packets = decoder.feed(actual)
        got = [p.encode().hex() for p in packets]
        if decoder.buffer or len(got) != len(expected) or sorted(got) != sorted(expected):
            raise AssertionError("actual RTL packet result/ID mismatch")
        if len({(p.id,p.payload[:6]) for p in packets}) != 32:
            raise AssertionError("duplicate result IDs")
        audit.update(backend="XSIM_REAL_RTL_NOT_BOARD", cores=args.cores, cost=args.cost,
                     input_sha256=hashlib.sha256(raw).hexdigest(),
                     output_sha256=hashlib.sha256(actual).hexdigest(), results=len(packets), status="pass")
        (out / "udp_audit.json").write_text(json.dumps(audit, indent=2))
        (out / "windows_received.bin").write_bytes(actual)
        print(f"UDP_RTL_PASS cores={args.cores} cost={args.cost} results={len(packets)}", flush=True)
    finally:
        server.stop.set()
        thread.join()
        if server.error:
            raise server.error


if __name__ == "__main__":
    main()
