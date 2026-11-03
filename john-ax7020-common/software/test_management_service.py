import json
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
NODE = ROOT / "linux" / "node"
sys.path.insert(0, str(NODE))
import john_manage_service as daemon
import john_management as auth
import john_udp_protocol as proto


class ManagementServiceTest(unittest.TestCase):
    def setUp(self):
        self.key = b"K" * 32
        self.service = daemon.ManagementService(self.key, "/unused",
                                                "/usr/sbin/john-bitstream", 42000)
        self.sequence = 7
        self.session = 8

    def request(self, msg_type, action, nonce=None, **values):
        body = {"action": action, "timestamp": int(time.time()),
                "nonce": nonce or ("%032x" % self.sequence)}
        body.update(values)
        return proto.Message(
            msg_type, session=self.session, sequence=self.sequence,
            payload=auth.encode(body, self.key, self.session, self.sequence),
        )

    def decode_reply(self, response):
        return auth.decode(response.payload, self.key, self.session,
                           self.sequence, max_age=60)

    def test_caps_is_authenticated_and_reports_allowlist(self):
        manifest = {"firmware": "md5.bin", "algorithm": 3,
                    "register_abi": 0x10001, "stream_abi": 0x10000}
        with patch.object(self.service, "manifests", return_value={3: (Path("m.json"), manifest)}), \
                patch.object(daemon.john_bitstream, "health", return_value={"bitstream": {"algorithm": 3}}):
            response = self.service.dispatch(self.request(proto.MANAGE_CAPS, "caps"))
        values = self.decode_reply(response)
        self.assertEqual(values["loaded_algorithm"], 3)
        self.assertEqual(values["algorithms"][0]["name"], "md5crypt8")

    def test_exact_udp_retry_returns_cached_response(self):
        request = self.request(proto.MANAGE_STATUS, "status")
        first = self.service.dispatch(request)
        second = self.service.dispatch(request)
        self.assertEqual(first.encode(), second.encode())

    def test_nonce_reuse_with_new_sequence_is_rejected(self):
        nonce = "n" * 32
        self.service.dispatch(self.request(proto.MANAGE_STATUS, "status", nonce=nonce))
        self.sequence += 1
        with self.assertRaisesRegex(RuntimeError, "replayed"):
            self.service.dispatch(self.request(proto.MANAGE_STATUS, "status", nonce=nonce))

    def test_wrong_key_is_rejected(self):
        request = self.request(proto.MANAGE_STATUS, "status")
        request.payload = auth.encode(
            {"action": "status", "timestamp": int(time.time()), "nonce": "x" * 32},
            b"Z" * 32, self.session, self.sequence)
        with self.assertRaises(PermissionError):
            self.service.dispatch(request)

    def test_switch_uses_manifest_path_not_user_path(self):
        manifest = {"firmware": "md5.bin", "algorithm": 3,
                    "register_abi": 0x10001, "stream_abi": 0x10000}
        path = Path("/etc/john/bitstreams/md5.json")
        request = self.request(proto.MANAGE_SWITCH, "switch", algorithm=3,
                               recover=False, drain_seconds=10, path="/tmp/evil")
        with patch.object(self.service, "manifests", return_value={3: (path, manifest)}), \
                patch.object(daemon.threading, "Thread") as thread:
            response = self.service.dispatch(request)
        args = thread.call_args.kwargs["args"]
        self.assertEqual(args[2], path)
        self.assertEqual(self.decode_reply(response)["operation"]["algorithm"], 3)


if __name__ == "__main__":
    unittest.main()
