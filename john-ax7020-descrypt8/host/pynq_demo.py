"""PYNQ 2.4 board helper. NOT board-tested. One outstanding DMA transaction.

Only call with a freshly configured overlay after any exception/reset.
No network listener or remote bitstream loader is provided.
"""
import time
from codec8 import encode_superbatch, decode_superresult, verify_superresult

class DescryptDevice:
    def __init__(self, overlay):
        from pynq import Xlnk, MMIO
        import numpy as np
        self._np = np
        self.overlay = overlay
        self.dma = MMIO(overlay.ip_dict['dma']['phys_addr'], 0x1000)
        self.status = MMIO(overlay.ip_dict['status']['phys_addr'], 0x1000)
        self.allocator = Xlnk()
        self.tx = self.allocator.cma_array(shape=(290,), dtype=np.uint32)
        self.rx = self.allocator.cma_array(shape=(42,), dtype=np.uint32)
        self.poisoned = False
        self.dma.write(0x00, 1)
        self.dma.write(0x30, 1)

    def compute(self, groups, targets, transaction_id, timeout=5.0):
        if self.poisoned:
            raise RuntimeError('Reconfigure PL after failed session; buffers retained')
        payload = encode_superbatch(groups, targets, transaction_id)
        state = self.status.read(0)
        if state >> 24 != 0xd8 or state & 0xffffff:
            raise RuntimeError('PL not idle/healthy: 0x%08x' % state)
        self.tx[:] = self._np.frombuffer(payload, dtype='<u4')
        self.tx.flush()
        self.rx[:] = 0
        self.rx.flush()
        started = time.monotonic()
        self.poisoned = True
        # Clear completion IRQs, then arm receive before sending.
        self.dma.write(0x34, 0x7000)
        self.dma.write(0x04, 0x7000)
        self.dma.write(0x48, self.rx.physical_address)
        self.dma.write(0x58, 168)
        self.dma.write(0x18, self.tx.physical_address)
        self.dma.write(0x28, 1160)
        while True:
            txs, rxs = self.dma.read(0x04), self.dma.read(0x34)
            state = self.status.read(0)
            if (txs | rxs) & 0x70 or state & 0xff0006:
                raise RuntimeError('DMA/PL fault; reload overlay')
            if txs & 0x1000 and rxs & 0x1000:
                break
            if time.monotonic()-started > timeout:
                raise TimeoutError('DMA timeout; buffers kept alive, reload overlay')
            time.sleep(0.001)
        self.rx.invalidate()
        result = decode_superresult(self.rx.tobytes(),transaction_id)
        result['elapsed_seconds'] = time.monotonic()-started
        verify_superresult(groups,targets,result)
        self.poisoned = False
        return result
