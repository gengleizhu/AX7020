"""生成可审计的John接口移植副本；原算法、解析器及仲裁器不改动。"""
from pathlib import Path
import difflib
import json
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from john_packet_codec import Packet


def main():
    src = (ROOT / "rtl/john_original/bcrypt/bcrypt.v").read_text()
    # 只取真实实现，避免ISE黑盒分支；宏SIMULATION仍必须用于原Core。
    text = src.split("`ifdef\tSIMULATION", 1)[1].split("`else", 1)[0]
    text = '`include "bcrypt.vh"\n' + text
    text = text.replace("module bcrypt #(", "module john_stream_engine #(", 1)
    text = text.replace("input [15:0] hs_input_din,", "input [7:0] hs_input_din,")
    begin = text.index("\tinput_fifo input_fifo(")
    end = text.index("\n\t);", begin) + len("\n\t);")
    text = text[:begin] + """
    // 上游由AXI串行器保持字节，直接使用原解析器的消费条件。
    assign din = hs_input_din;
    wire empty = ~hs_input_wr_en;
    assign hs_input_almost_full = ~rd_en;
    assign hs_input_prog_full = ~rd_en;
""" + text[end:]
    dest = ROOT / "rtl/integration"
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "john_stream_engine.v").write_text(text)
    (dest / "john_stream_engine.patch").write_text("".join(difflib.unified_diff(
        src.splitlines(True), text.splitlines(True),
        "john_original/bcrypt/bcrypt.v", "integration/john_stream_engine.v")))
    # 32个候选覆盖8核多轮调度，两个不同口令相同salt；来自阶段1已知答案。
    records = json.loads((ROOT / "sim/vectors/vectors.json").read_text())
    for cost in (4, 5):
        # cost5使用相同已知salt/口令，独立参考仅用于检查，不参与返回路径。
        sys.path.insert(0, str(ROOT / "scripts"))
        from prepare import decode64, reference
        salt = decode64(records[7]["hash"][7:29], 16)
        config = struct.pack("<4I", *struct.unpack(">4I", salt)) + b"a" + struct.pack("<I", 1 << cost) + b"\0\0\xcc"
        words = [b"01234567" if i % 2 == 0 else b"012345678" for i in range(32)]
        packets = [Packet(3, 0, config), Packet(2, 0x3456 + cost, b"\0"*5+b"\xbb"),
                   Packet(1, 0x3456 + cost, b"".join(w+b"\0" for w in words))]
        raw = b"".join(p.encode() for p in packets)
        results = {w: reference(w, salt, cost) for w in set(words)}
        expected = []
        for i, word in enumerate(words):
            payload = struct.pack("<HI", i, 0) + struct.pack("<6I", *struct.unpack(">6I", results[word]))
            expected.append(Packet(0xd3, 0x3456 + cost, payload, b"\xb9\x35\0").encode().hex())
        folder = ROOT / f"sim/integration/cost{cost}"
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "input.bin").write_bytes(raw)
        (folder / "input.mem").write_text("".join(f"{b:02x}\n" for b in raw))
        (folder / "expected.json").write_text(json.dumps(expected, indent=2))
        (folder / "metadata.json").write_text(json.dumps({"bytes": len(raw), "results": len(words), "cost": cost}))
    print("INTEGRATION_PREPARE_PASS")


if __name__ == "__main__":
    main()
