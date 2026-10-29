"""固定源码、生成自检数据。软件参考仅用于验证，绝不作为FPGA返回结果。"""
from pathlib import Path
import hashlib
import difflib
import json
import re
import shutil
import struct
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
JOHN = ROOT / "third_party/john"
SRC = JOHN / "src/ztex/fpga-bcrypt"
PIN = "5184bc0b8c105f8c5978b112e723d65b2de3e63e"
sys.path.insert(0, str(ROOT / "host"))
from john_packet_codec import Packet


def read_constants():
    # Independent source: CPU BF_common.c, not the hardware S_data.txt.
    text = (JOHN / "src/BF_common.c").read_text()
    start = text.index("0xd1310ba6")
    vals = [int(x, 16) for x in re.findall(r"0x[0-9a-fA-F]{8}", text[start:])]
    return vals


P0 = [0x243f6a88,0x85a308d3,0x13198a2e,0x03707344,0xa4093822,0x299f31d0,
      0x082efa98,0xec4e6c89,0x452821e6,0x38d01377,0xbe5466cf,0x34e90c6c,
      0xc0ac29b7,0xc97c50dd,0x3f84d5b5,0xb5470917,0x9216d5d9,0x8979fb1b]
B64 = "./ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789"
MASK = 0xffffffff


def decode64(s, n):
    bits = "".join(f"{B64.index(c):06b}" for c in s)
    return bytes(int(bits[i:i+8], 2) for i in range(0, n*8, 8))


def expanded_key(password, bug=False):
    key = password[:72]
    if len(key) < 72:
        key += b"\0"
    out, j = [], 0
    for _ in range(18):
        w = 0
        for _ in range(4):
            b = key[j]
            j = (j+1) % len(key)
            w = ((w << 8) | (b-256 if bug and b & 128 else b)) & MASK
        out.append(w)
    return out


def reference(password, salt, cost, bug=False):
    """直观EksBlowfish参考，与RTL微码/流水结构独立；返回完整24字节。"""
    p, s = P0.copy(), read_constants()[:1024]
    key = expanded_key(password, bug)
    salt_words = list(struct.unpack(">4I", salt))

    def encrypt(l, r):
        for i in range(16):
            l ^= p[i]
            f = (((s[l >> 24] + s[256 + ((l >> 16) & 255)]) & MASK)
                 ^ s[512 + ((l >> 8) & 255)])
            r ^= (f + s[768 + (l & 255)]) & MASK
            l, r = r, l
        return r ^ p[17], l ^ p[16]

    def expand(words, salts):
        for i in range(18):
            p[i] ^= words[i % len(words)]
        l = r = j = 0
        for arr in (p, s):
            for i in range(0, len(arr), 2):
                if salts:
                    l ^= salts[j % 4]
                    r ^= salts[(j+1) % 4]
                    j += 2
                l, r = encrypt(l, r)
                arr[i], arr[i+1] = l, r

    expand(key, salt_words)
    for _ in range(1 << cost):
        expand(key, None)
        expand(salt_words, None)
    output = []
    words = struct.unpack(">6I", b"OrpheanBeholderScryDoubt")
    for i in range(0, 6, 2):
        l, r = words[i:i+2]
        for _ in range(64):
            l, r = encrypt(l, r)
        output += [l, r]
    return struct.pack(">6I", *output)


def write_mem(path, values, width=8):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(f"{v:0{width}x}\n" for v in values), encoding="ascii")


def main():
    actual = subprocess.check_output(["git", "-C", str(JOHN), "rev-parse", "HEAD"], text=True).strip()
    if actual != PIN:
        raise RuntimeError(f"unexpected upstream revision: {actual}")
    if subprocess.check_output(["git", "-C", str(JOHN), "status", "--porcelain"], text=True).strip():
        raise RuntimeError("upstream checkout modified")
    dest = ROOT / "rtl/john_original"
    shutil.copytree(SRC, dest, dirs_exist_ok=True)
    shutil.copy2(JOHN / "LICENSE", dest / "LICENSE")
    # 上游bcrypt版本遗漏了此寄存器声明；其它John算法的同源模块有声明。
    original = (SRC / "pkt_comm/word_gen_b.v").read_text()
    anchor = "reg [7:0] cur_range_count = 0;"
    assert original.count(anchor) == 1
    patched = original.replace(anchor, "reg [7:0] cur_range_count = 0, cur_range_count_max = 0;")
    compat = ROOT / "rtl/stage1"
    compat.mkdir(parents=True, exist_ok=True)
    (compat / "word_gen_b.v").write_text(patched)
    (compat / "word_gen_b.patch").write_text("".join(difflib.unified_diff(
        original.splitlines(True), patched.splitlines(True),
        "john_original/pkt_comm/word_gen_b.v", "stage1/word_gen_b.v")))
    hashes = {str(p.relative_to(dest)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest()
              for p in sorted(dest.rglob("*")) if p.is_file()}
    (ROOT / "reports").mkdir(exist_ok=True)
    (ROOT / "reports/source_manifest.json").write_text(json.dumps(
        {"repository": "https://github.com/gengleizhu/john", "branch": "bleeding-jumbo",
         "commit": PIN, "sha256": hashes}, indent=2))
    sd = [int(x,16) for x in re.findall(r"\b[0-9a-fA-F]{8}\b", (SRC / "bcrypt/S_data.txt").read_text())]
    assert len(sd) == 1024 and sd == read_constants()[:1024], "CPU/RTL S constants mismatch"
    vectors = [
        ("legacy", b"abcde", "$2a$00$////////..............XiwFBK8OLIKiLUZR11iwkDeHZvypH9y"),
        ("ascii", b"U*U*", "$2a$05$CCCCCCCCCCCCCCCCCCCCC.VGOzA784oUp/Z0DY336zx7pLYAy0lwK"),
        ("empty", b"", "$2a$05$CCCCCCCCCCCCCCCCCCCCC.7uG0VCzI2bS7j6ymqJi9CdcdxiRTWNy"),
        ("version_b", b"U*U*U", "$2b$05$XXXXXXXXXXXXXXXXXXXXXOAcXxm9kjPGEMsLznoKqmqw7tc8WCx4a"),
        ("version_x", b"\xa3", "$2x$05$/OK.fbVrR/bpIqNJ5ianF.CE5elHaaO4EbggVDjb8P19RukzXSM3e"),
        ("version_y", b"\xa3", "$2y$05$/OK.fbVrR/bpIqNJ5ianF.Sa7shbm4.OzKpvFnX1pQLmQW96oUlCq"),
        ("len72", b"\xaa"*72, "$2a$05$/OK.fbVrR/bpIqNJ5ianF.swQOIzjOiJ9GHEPuhEkvqrUyvWhEMx6"),
        ("len8", b"01234567", "$2a$04$pIqNJ/d3.iUtNb........1ynmOuHkBNwBW8zbBj6wTB8XX4/HPiy"),
        ("len9", b"012345678", "$2a$04$pIqNJ/d3.iUtNb........12LxxKuTok3B2V5Qedwkj.KlH.1uvye"),
    ]
    init = P0 + [0]*6 + list(struct.unpack(">6I", b"OrpheanBeholderScryDoubt"))
    # Hardware PN stores each magic-word pair reversed.
    init[24:30] = [init[i ^ 1] for i in range(24,30)]
    write_mem(ROOT / "sim/vectors/init.mem", init + sd)
    records = []
    combined, expect_packets, job_ends, job_counts = b"", [], [], []
    for idx, (name, pw, h) in enumerate(vectors):
        cost, bug = int(h[4:6]), h[2] == "x"
        salt = decode64(h[7:29], 16)
        out = reference(pw, salt, cost, bug)
        assert out[:23] == decode64(h[29:], 23), (name, out.hex(), decode64(h[29:],23).hex())
        ek = expanded_key(pw, bug)
        packet_id, word_id, gen_id = 0x1200+idx, 0x3400+idx, 0x56780000+idx
        data = ek + [64, 1 << cost] + list(struct.unpack(">4I", salt)) + [(packet_id << 16)|word_id, gen_id] + [0]*5
        expected = [(packet_id << 16)|word_id, gen_id] + list(struct.unpack(">6I", out))
        write_mem(ROOT / f"sim/vectors/data_{idx}.mem", data)
        write_mem(ROOT / f"sim/vectors/result_{idx}.mem", expected)
        write_mem(ROOT / f"sim/vectors/key_{idx}.mem", list(pw[:72]) + [0]*(73-len(pw[:72])), 2)
        write_mem(ROOT / f"sim/vectors/ek_{idx}.mem", ek)
        salt_le = struct.pack("<4I", *struct.unpack(">4I", salt))
        config = salt_le + h[2].encode() + struct.pack("<I", 1 << cost) + b"\0\0\xcc"
        word = pw[:72] + (b"\0" if len(pw) < 72 else b"")
        packets = Packet(3,0,config).encode() + Packet(2,packet_id,b"\0"*5+b"\xbb").encode() + Packet(1,packet_id,word).encode()
        write_mem(ROOT / f"sim/vectors/packet_{idx}.mem", packets, 2)
        combined += packets
        # Original RESULT uses Word ID 0 / Generation ID 0 for pass-through.
        expect_packets.append(Packet(0xd3, packet_id, b"\0"*6 + struct.pack("<6I", *struct.unpack(">6I",out)), b"\xb9\x35\0").encode().hex())
        job_ends.append(len(combined))
        job_counts.append(len(expect_packets))
        records.append(dict(index=idx,name=name,password_hex=pw.hex(),hash=h,cost=cost,bug=bug,
                            full_result_be=out.hex(),packet_bytes=len(packets)))
        print(f"REFERENCE_PASS {name} cost={cost} full24={out.hex()}", flush=True)
    # 同一salt批次内两个候选：第二个在第一个BUSY时已缓存，检查Word ID 0/1。
    h = vectors[7][2]
    salt = decode64(h[7:29],16)
    cfg = struct.pack("<4I", *struct.unpack(">4I",salt)) + b"a" + struct.pack("<I",16) + b"\0\0\xcc"
    combined += (Packet(3,0,cfg).encode() + Packet(2,0x2345,b"\0"*5+b"\xbb").encode()
                 + Packet(1,0x2345,b"01234567\0"+b"012345678\0").encode())
    for word_id, vector_idx in enumerate((7,8)):
        out = bytes.fromhex(records[vector_idx]["full_result_be"])
        payload = struct.pack("<HI",word_id,0) + struct.pack("<6I",*struct.unpack(">6I",out))
        expect_packets.append(Packet(0xd3,0x2345,payload,b"\xb9\x35\0").encode().hex())
    job_ends.append(len(combined))
    job_counts.append(len(expect_packets))
    write_mem(ROOT / "sim/vectors/job_ends.mem",job_ends)
    write_mem(ROOT / "sim/vectors/job_counts.mem",job_counts)
    write_mem(ROOT / "sim/vectors/packets.mem", combined + (b"\0" if len(combined)%2 else b""), 2)
    (ROOT / "sim/vectors/vectors.json").write_text(json.dumps(records, indent=2))
    (ROOT / "sim/vectors/expected_packets.json").write_text(json.dumps(expect_packets, indent=2))
    (ROOT / "sim/vectors/config.vh").write_text(
        f"`define VECTOR_COUNT {len(records)}\n`define JOB_COUNT {len(job_ends)}\n"
        f"`define RESULT_COUNT {len(expect_packets)}\n`define INPUT_BYTES {(len(combined)+1)//2*2}\n")
    print(f"PREPARE_PASS vectors={len(records)}")


if __name__ == "__main__":
    main()
