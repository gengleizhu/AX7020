"""Exercise admission restoration and fail-closed transition ordering."""
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux' / 'node'))
import john_bitstream as loader


class SwitchTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        for name in ('dma', 'manager'):
            (root / name).mkdir()
        (root / 'manager' / 'state').write_text('operating')
        self.marker = root / 'maintenance'
        self.patches = patch.multiple(loader, MAINTENANCE=self.marker,
                                     DMA=root / 'dma', MANAGER=root / 'manager')
        self.patches.start()
        self.addCleanup(self.patches.stop)
        self.manifest = {'firmware': 'test.bin', 'algorithm': 3}
        self.info = {'service': {'maintenance': True, 'tasks_tracked': 0},
                     'dma': {'running': 0}, 'bitstream': {'algorithm': 3}}

    def test_drain_timeout_preserves_service(self):
        self.info['service']['tasks_tracked'] = 1
        with patch.object(loader, 'health', return_value=self.info), patch.object(loader, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'drain timeout'):
                loader.switch(self.manifest, 42000, 0)
            run.assert_not_called()
        self.assertFalse(self.marker.exists())

    def test_stop_failure_keeps_admission_closed(self):
        with patch.object(loader, 'health', return_value=self.info), patch.object(loader, 'run', side_effect=RuntimeError('stop failed')):
            with self.assertRaisesRegex(RuntimeError, 'stop failed'):
                loader.switch(self.manifest, 42000, 0)
        self.assertTrue(self.marker.exists())

    def test_identity_failure_never_restarts_service(self):
        with patch.object(loader, 'health', return_value=self.info), patch.object(loader, 'run') as run, patch.object(loader, 'identify', side_effect=RuntimeError('wrong ABI')):
            with self.assertRaisesRegex(RuntimeError, 'wrong ABI'):
                loader.switch(self.manifest, 42000, 0)
            self.assertEqual([c.args for c in run.call_args_list],
                             [('/etc/init.d/john-node', 'stop'), ('rmmod', 'john_dma')])
        self.assertTrue(self.marker.exists())

    def test_success_reopens_admission_last(self):
        with patch.object(loader, 'health', return_value=self.info), patch.object(loader, 'run') as run, patch.object(loader, 'identify', return_value=0x10011):
            loader.switch(self.manifest, 42000, 0)
            self.assertEqual(run.call_args_list[-1].args, ('/etc/init.d/john-node', 'start'))
        self.assertFalse(self.marker.exists())

    def test_recovery_requires_failed_transition(self):
        with patch.object(loader, 'run') as run:
            with self.assertRaisesRegex(RuntimeError, 'recovery requires'):
                loader.recover(self.manifest, 42000)
            run.assert_not_called()

    def test_recovery_identity_failure_keeps_closed(self):
        self.marker.write_text('loading')
        with patch.object(loader, 'run') as run, patch.object(loader, 'identify', side_effect=RuntimeError('wrong ABI')):
            with self.assertRaisesRegex(RuntimeError, 'wrong ABI'):
                loader.recover(self.manifest, 42000)
            self.assertNotIn(('/etc/init.d/john-node', 'start'), [c.args for c in run.call_args_list])
        self.assertTrue(self.marker.exists())

    def test_recovery_restores_service_then_reopens(self):
        self.marker.write_text('loading')
        with patch.object(loader, 'run') as run, patch.object(loader, 'identify', return_value=0x10011), patch.object(loader, 'health', return_value=self.info):
            loader.recover(self.manifest, 42000)
            self.assertEqual(run.call_args_list[-1].args, ('/etc/init.d/john-node', 'start'))
        self.assertFalse(self.marker.exists())


if __name__ == '__main__':
    unittest.main()
