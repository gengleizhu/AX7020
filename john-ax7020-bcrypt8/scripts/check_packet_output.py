"""核对RTL实际返回的每一个字节，不将参考答案填入仿真输出。"""
import json
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "host"))
from john_packet_codec import Decoder

actual = bytes(int(line, 16) for line in (ROOT / "reports/stage1/packet_output.hex").read_text().splitlines())
expected = [bytes.fromhex(x) for x in json.loads((ROOT / "sim/vectors/expected_packets.json").read_text())]
decoder = Decoder()
packets = decoder.feed(actual)
assert not decoder.buffer, "trailing incomplete packet"
assert len(packets) == len(expected), f"got {len(packets)} expected {len(expected)}"
assert actual == b"".join(expected), "RTL packet differs from expected bytes"
for i, p in enumerate(packets):
    print(f"RTL_PACKET_PASS index={i} type=0x{p.type:02x} packet_id=0x{p.id:04x} bytes={len(p.encode())}")
print("STAGE1_PACKET_BYTES_PASS")
