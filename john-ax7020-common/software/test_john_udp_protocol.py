import importlib.util
from pathlib import Path
import sys
import unittest


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "linux" / "node" / "john_udp_protocol.py"
SPEC = importlib.util.spec_from_file_location("john_udp_protocol", MODULE_PATH)
protocol = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = protocol
SPEC.loader.exec_module(protocol)


class ProtocolTest(unittest.TestCase):
    def test_round_trip(self):
        original = protocol.Message(
            msg_type=protocol.DATA,
            flags=3,
            session=0x12345678,
            sequence=19,
            task_lo=0x89ABCDEF,
            task_hi=0x01234567,
            shard=7,
            batch=11,
            offset=1024,
            total_len=10056,
            code=0,
            payload=bytes(range(251)) * 4,
        )
        self.assertEqual(protocol.decode(original.encode()), original)
        self.assertEqual(original.task, 0x0123456789ABCDEF)

    def test_header_crc_detects_corruption(self):
        encoded = bytearray(protocol.Message(msg_type=protocol.STATUS).encode())
        encoded[20] ^= 0x01
        with self.assertRaisesRegex(ValueError, "header CRC"):
            protocol.decode(encoded)

    def test_payload_crc_detects_corruption(self):
        encoded = bytearray(
            protocol.Message(msg_type=protocol.DATA, payload=b"payload").encode()
        )
        encoded[-1] ^= 0x01
        with self.assertRaisesRegex(ValueError, "payload CRC"):
            protocol.decode(encoded)

    def test_mtu_limit(self):
        with self.assertRaisesRegex(ValueError, "MTU"):
            protocol.Message(
                msg_type=protocol.DATA,
                payload=b"x" * (protocol.MAX_PAYLOAD + 1),
            ).encode()

    def test_reply_preserves_identity(self):
        request = protocol.Message(
            msg_type=protocol.COMMIT,
            session=9,
            sequence=10,
            task_lo=11,
            task_hi=12,
            shard=13,
            batch=14,
        )
        response = protocol.reply(request, protocol.ACK)
        self.assertEqual(
            (response.session, response.sequence, response.task_lo,
             response.task_hi, response.shard, response.batch),
            (9, 10, 11, 12, 13, 14),
        )


if __name__ == "__main__":
    unittest.main()
