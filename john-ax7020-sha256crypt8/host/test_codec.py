import struct
import unittest
from codec import *

class CodecTests(unittest.TestCase):
    def test_known_default_vector(self):
        self.assertEqual(
            crypt_string(b'Hello world!', b'saltstring', 5000),
            '$5$saltstring$5B8vYYiY.CVt1RlTTf8KbXBH3hsxY/GNooZaBBGWEc5')
        self.assertEqual(digest(b'Hello world!', b'saltstring', 5000).hex(),
                         'ece9807faae7f7203489a324e617df4c8b649a234792134358d845655d4d107a')
        self.assertEqual(hardware_words(digest(b'Hello world!', b'saltstring', 5000))[0],
                         0x7f80e9ec)

    def test_packet_sizes_and_validation(self):
        jobs = [(bytes([65 + i % 20]), b'salt', i, 1000) for i in range(96)]
        frame = encode_batch(jobs, 7)
        self.assertEqual(len(frame), 9992)
        self.assertEqual(struct.unpack_from('<2I', frame), (REQUEST_MAGIC, 7))
        for bad in (0, 1_000_000_000):
            with self.assertRaises(ValueError):
                digest(b'x', b's', bad)
        with self.assertRaises(ValueError): encode_job(b'x',b's',1,999)
        with self.assertRaises(ValueError): digest(b'x' * 33, b's')

    def test_decode_layout(self):
        words = [RESPONSE_MAGIC, 9]
        for unit in range(8):
            words += [unit, UNIT_MAGIC, 100 + unit]
            for job in range(12):
                words += [unit * 12 + job, 0] + [unit * 100 + job] * 8
        decoded = decode_result(struct.pack('<986I', *words), 9)
        self.assertEqual(decoded[7]['records'][11][0], 95)
        self.assertEqual(len(decoded[0]['records'][0][1]), 32)
        self.assertEqual(decoded[0]['records'][0][1][:4], struct.pack('<I', 0))

if __name__ == '__main__': unittest.main()
