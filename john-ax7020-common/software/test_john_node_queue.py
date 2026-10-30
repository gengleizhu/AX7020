import importlib.util
from pathlib import Path
import struct
import sys
import threading
import time
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE_DIR = ROOT / "linux" / "node"
sys.path.insert(0, str(NODE_DIR))

SPEC = importlib.util.spec_from_file_location(
    "john_node_service", NODE_DIR / "john_node_service.py"
)
service = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = service
SPEC.loader.exec_module(service)
proto = service.proto


class FakeHardware:
    max_tx = service.MAX_REQUEST
    max_rx = service.MAX_RESPONSE

    def __init__(self):
        self.gate = threading.Event()
        self.gate.set()
        self.runs = 0

    def close(self):
        pass

    def identify(self):
        return {
            "algorithm": 3, "units": 8, "cores": 3,
            "clock_hz": 100000000, "capabilities": 3,
            "status": 0x11, "build_date": 20261030,
            "register_abi": service.REGISTER_ABI,
            "stream_abi": service.STREAM_ABI, "native_status": 1,
        }

    def dma_stats(self):
        return {
            "tx_completions": self.runs,
            "rx_completions": self.runs,
            "running": 0,
        }

    def validate_request(self, request):
        header = service.COMMON_HEADER.unpack_from(request)
        if header[3] != len(request) or header[4] != 3:
            raise ValueError("bad request")
        return header, 64

    def run(self, request, timeout_ms):
        self.gate.wait(2)
        self.runs += 1
        return bytes(64), {
            "completed_lo": 1, "completed_hi": 0,
            "cycles_lo": 100, "cycles_hi": 0, "status": 4,
        }


def make_request(task, batch):
    words = [0] * 16
    words[0:5] = [service.STREAM_MAGIC, service.STREAM_ABI, 64, 64, 3]
    words[6] = task
    words[8] = 1
    words[9] = batch
    return struct.pack("<16I", *words)


def message(kind, session, task, batch, **kwargs):
    return proto.Message(
        kind, session=session, task_lo=task, shard=1, batch=batch, **kwargs
    )


class QueueTest(unittest.TestCase):
    def setUp(self):
        self.hardware = FakeHardware()
        self.node = service.Node(
            self.hardware, 1000, queue_depth=2, result_depth=2,
            result_ttl=60, interface="lo", node_id="test-node",
        )

    def tearDown(self):
        self.hardware.gate.set()
        self.node.close()

    def submit(self, session, task, batch):
        request = make_request(task, batch)
        begin = message(
            proto.BEGIN, session, task, batch, total_len=len(request)
        )
        self.assertEqual(self.node.begin(begin), proto.OK)
        data = message(
            proto.DATA, session, task, batch, total_len=len(request),
            payload=request,
        )
        self.assertEqual(self.node.data(data), proto.OK)
        commit = message(
            proto.COMMIT, session, task, batch, total_len=len(request)
        )
        self.assertEqual(self.node.commit(commit), proto.OK)
        return commit

    def wait_state(self, msg, expected):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            task = self.node.tasks.get(service.task_key(msg))
            if task and task.state == expected:
                return task
            time.sleep(0.005)
        self.fail(f"task did not reach state {expected}")

    def test_two_tasks_queue_and_release_results(self):
        first = self.submit(1, 101, 1)
        second = self.submit(2, 102, 2)
        self.wait_state(first, proto.STATE_DONE)
        self.wait_state(second, proto.STATE_DONE)
        self.assertEqual(self.hardware.runs, 2)
        self.assertEqual(self.node._result_count_locked(), 2)
        self.assertEqual(self.node.release_result(first), proto.OK)
        self.assertEqual(self.node.release_result(second), proto.OK)
        self.assertEqual(self.node.release_result(second), proto.OK)
        self.assertEqual(len(self.node.tasks), 0)

    def test_queue_full_is_explicit(self):
        self.hardware.gate.clear()
        self.submit(1, 101, 1)
        self.submit(2, 102, 2)
        third = message(proto.BEGIN, 3, 103, 3, total_len=64)
        self.assertEqual(self.node.begin(third), proto.ERR_QUEUE_FULL)

    def test_health_and_heartbeat_fit_one_datagram(self):
        time.sleep(0.02)
        self.assertLessEqual(len(self.node.health_payload()), proto.MAX_PAYLOAD)
        self.assertEqual(
            len(self.node.heartbeat_payload()), service.HEARTBEAT_WORDS.size
        )


if __name__ == "__main__":
    unittest.main()
