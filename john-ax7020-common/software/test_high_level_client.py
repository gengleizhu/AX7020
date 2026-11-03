import struct
import sys
from pathlib import Path
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "john-ax7020-common" / "host"))
import john_fpga_client as sdk


def common_response(prepared, payload):
    batch = prepared.batch
    flags = (1 if batch.algorithm == 2 else 0) | (2 if batch.valid_count < batch.physical_count else 0)
    records = 8 if batch.algorithm == 2 else batch.physical_count
    header = [
        0x3152544A, 0x10000, 64, 64 + len(payload), batch.algorithm,
        0x100 + batch.algorithm, batch.task & 0xFFFFFFFF, batch.task >> 32,
        batch.shard, batch.batch, 0, batch.valid_count, len(payload), records,
        flags, 0,
    ]
    return struct.pack("<16I", *header) + payload


def digest_payload(prepared, codec, response_magic, unit_magic, units, per_unit, size):
    batch = prepared.batch
    salt = b"salt1234"
    values = [b"password"] + [b""] * (batch.physical_count - 1)
    data = struct.pack("<2I", response_magic, batch.batch)
    for unit in range(units):
        data += struct.pack("<3I", unit, unit_magic, 100)
        for local in range(per_unit):
            index = unit * per_unit + local
            if batch.algorithm == 3:
                raw = codec.digest(values[index], salt)
            else:
                raw = codec.digest(values[index], salt, 1000)
            data += struct.pack("<Q", index + 1) + raw
    assert len(data) == size
    return data


class HighLevelClientTest(unittest.TestCase):
    def test_all_five_prepare_with_common_api(self):
        cases = [
            ("bcrypt", ["01234567"], "$2a$04$pIqNJ/d3.iUtNb........1ynmOuHkBNwBW8zbBj6wTB8XX4/HPiy", 1),
            ("descrypt", [""], "..X8NBuQ4l6uQ", 2),
            ("md5crypt", ["password"], "$1$salt1234$HJCsv4hSeVLHo3hVyl4nh0", 3),
            ("sha256crypt", ["password"], "$5$rounds=1000$salt1234$aMT3fONWDA1J3Ndh7sjwgpNo6J/43lD0riI3tf2YYh2", 4),
            ("sha512crypt", ["password"], "$6$rounds=1000$salt1234$SVDFHbJXYrzjGi2fA1k3ws01/D9q0ZTAh1KfRF5.ehgjVBqfHUaKqfynXefJ4DxIWxkMAITYq9mmcBl938YQ//", 5),
        ]
        for name, candidates, target, number in cases:
            prepared = sdk.prepare_batch(name, candidates, target=target,
                                         task_id=1, batch_id=2)
            prepared.batch.validate()
            self.assertEqual(prepared.algorithm, number)
            self.assertEqual(struct.unpack_from("<I", prepared.request())[0], 0x3151544A)

    def test_bcrypt_result_is_mapped_and_matched(self):
        target = "$2a$04$pIqNJ/d3.iUtNb........1ynmOuHkBNwBW8zbBj6wTB8XX4/HPiy"
        prepared = sdk.prepare_batch("bcrypt", ["01234567"], target=target,
                                     task_id=1, batch_id=2)
        expected = sdk._bcrypt_decode64(target[29:], 23) + b"\0"
        native = sdk.bcrypt_codec.Packet(
            0xD3, 2, struct.pack("<HI", 0, 0) +
            struct.pack("<6I", *struct.unpack(">6I", expected)), b"\xb9\x35\0"
        ).encode()
        records = prepared.decode_response(common_response(prepared, native))
        self.assertTrue(records[0]["matched"])

    def test_digest_results_drop_padding_and_match(self):
        cases = [
            ("md5crypt", "$1$salt1234$HJCsv4hSeVLHo3hVyl4nh0", sdk.md5_codec,
             0x38524D44, 0x38524D4A, 8, 12, 2408),
            ("sha256crypt", "$5$rounds=1000$salt1234$aMT3fONWDA1J3Ndh7sjwgpNo6J/43lD0riI3tf2YYh2", sdk.sha256_codec,
             0x38524853, 0x3853484A, 8, 12, 3944),
            ("sha512crypt", "$6$rounds=1000$salt1234$SVDFHbJXYrzjGi2fA1k3ws01/D9q0ZTAh1KfRF5.ehgjVBqfHUaKqfynXefJ4DxIWxkMAITYq9mmcBl938YQ//", sdk.sha512_codec,
             0x34524853, 0x3453484A, 4, 16, 4664),
        ]
        for name, target, codec, response_magic, unit_magic, units, per_unit, size in cases:
            prepared = sdk.prepare_batch(name, ["password"], target=target,
                                         task_id=1, batch_id=2)
            native = digest_payload(prepared, codec, response_magic, unit_magic,
                                    units, per_unit, size)
            records = prepared.decode_response(common_response(prepared, native))
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0]["matched"])

    def test_des_requires_full_verification(self):
        prepared = sdk.prepare_batch("descrypt", [""], target="..X8NBuQ4l6uQ",
                                     task_id=1, batch_id=2)
        native = struct.pack("<2I", 0x38524344, 2)
        native += b"".join(struct.pack("<5I", core, 0x31524344,
                                       1 if core == 0 else 0, 100,
                                       0xDC000001) for core in range(8))
        with patch.object(sdk.des_codec, "verify_matches", return_value=[0]):
            records = prepared.decode_response(common_response(prepared, native))
        self.assertTrue(records[0]["provisional"])
        self.assertTrue(records[0]["matched"])
        self.assertEqual(len(records), 1)


if __name__ == "__main__":
    unittest.main()
