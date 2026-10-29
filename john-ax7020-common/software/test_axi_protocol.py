import struct
import unittest
from axi_protocol import Batch, LAYOUT, MAGIC


class ProtocolTest(unittest.TestCase):
    def batch(self, algorithm):
        if algorithm == 1:
            return Batch(1, 0x123456789AB, 7, 123, 2, 2, b'example packet')
        n, size, _ = LAYOUT[algorithm]
        payload = struct.pack('<II', MAGIC[algorithm][0], 123) + bytes(size - 8)
        return Batch(algorithm, 0x123456789AB, 7, 123, n - 1, n, payload)

    def response(self, b):
        payload = bytes(b.output_bytes)
        if b.algorithm != 1:
            payload = struct.pack('<II', MAGIC[b.algorithm][1], b.batch) + payload[8:]
        h = [0x3152544A, 0x10000, 64, 64 + len(payload), b.algorithm, 256 + b.algorithm,
             b.task & 0xFFFFFFFF, b.task >> 32, b.shard, b.batch, 0, b.valid_count,
             len(payload), 8 if b.algorithm == 2 else b.physical_count,
             (b.algorithm == 2) | ((b.valid_count < b.physical_count) << 1), 0]
        return struct.pack('<16I', *h) + payload

    def test_all_layouts(self):
        for a in range(1, 6):
            b = self.batch(a)
            self.assertEqual(len(b.request()), 64 + len(b.payload))
            self.assertEqual(len(b.descriptor()), 18)
            response = self.response(b)
            self.assertEqual(len(b.parse_response(response)), b.output_bytes)
            with self.assertRaises(ValueError):
                b.parse_response(response[:-1])
            changed = bytearray(response)
            changed[36] ^= 1
            with self.assertRaises(ValueError):
                b.parse_response(changed)

    def test_invalid_algorithm(self):
        with self.assertRaises(ValueError):
            Batch(6, 1, 1, 1, 1, 1, b'').request()

    def test_invalid_count(self):
        with self.assertRaises(ValueError):
            Batch(1, 1, 1, 1, 171, 171, b'valid length').request()


if __name__ == '__main__':
    unittest.main()
