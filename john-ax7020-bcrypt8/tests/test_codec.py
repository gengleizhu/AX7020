import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from john_packet_codec import Packet, Decoder


class CodecTests(unittest.TestCase):
    def test_upstream_c_vectors(self):
        lines = (Path(__file__).parent / "c_packet_vectors.txt").read_text().splitlines()
        self.assertEqual(len(lines), 65)
        for n, line in enumerate(lines, 1):
            p = Packet(n % 4 + 1, 0x1234+n, bytes((i*137+n*19)&255 for i in range(n)))
            self.assertEqual(p.encode().hex(), line)

    def test_all_fragment_sizes(self):
        original = [Packet(1, n, bytes(range(n+1))) for n in range(40)]
        stream = b"".join(p.encode() for p in original)
        for size in (1, 2, 3, 7, 13, 14, 17, 1472):
            d, result = Decoder(), []
            for i in range(0, len(stream), size):
                result.extend(d.feed(stream[i:i+size]))
            self.assertEqual(result, original)
            self.assertFalse(d.buffer)

    def test_corruption(self):
        good = Packet(1, 5, b"abcde").encode()
        for i in range(len(good)):
            bad = bytearray(good)
            bad[i] ^= 1
            with self.assertRaises(ValueError):
                Decoder().feed(bad)

    def test_reserved_is_not_forced_zero(self):
        p = Packet(0xd3, 1, bytes(range(30)), b"\xb9\x35\0")
        self.assertEqual(Decoder().feed(p.encode()), [p])


if __name__ == "__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout, verbosity=2))
