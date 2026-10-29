"""PYNQ 2.4 helper. NOT board-tested. Reload overlay after any exception.

Example: device = Md5cryptDevice(Overlay('john_md5crypt8.bit'))
         result = device.compute(jobs, transaction_id=1)
jobs: exactly 96 (password_bytes, salt_bytes, unique_uint64_id) tuples.
"""
import time
from codec import encode_batch, decode_result, digest

class Md5cryptDevice:
    def __init__(self, overlay):
        from pynq import Xlnk, MMIO
        import numpy as np
        self.np = np
        self.overlay = overlay
        self.dma = MMIO(overlay.ip_dict['dma']['phys_addr'], 0x1000)
        self.status = MMIO(overlay.ip_dict['status']['phys_addr'], 0x1000)
        self.allocator = Xlnk()
        self.tx = self.allocator.cma_array(shape=(2498,), dtype=np.uint32)
        self.rx = self.allocator.cma_array(shape=(602,), dtype=np.uint32)
        self.poisoned = False
        self.dma.write(0x00, 1)
        self.dma.write(0x30, 1)

    def compute(self, jobs, transaction_id, timeout=5.0, verify=True):
        if self.poisoned:
            raise RuntimeError('Reload overlay after failed session; buffers retained')
        payload = encode_batch(jobs, transaction_id)
        state = self.status.read(0)
        if state != 0xa8000000:
            raise RuntimeError('PL not idle/healthy: 0x%08x' % state)
        self.tx[:] = self.np.frombuffer(payload, dtype='<u4')
        self.tx.flush()
        self.rx[:] = 0
        self.rx.flush()
        self.poisoned = True
        started = time.monotonic()
        self.dma.write(0x34, 0x7000)
        self.dma.write(0x04, 0x7000)
        self.dma.write(0x48, self.rx.physical_address)
        self.dma.write(0x58, 2408)
        self.dma.write(0x18, self.tx.physical_address)
        self.dma.write(0x28, 9992)
        while True:
            txs, rxs = self.dma.read(0x04), self.dma.read(0x34)
            state = self.status.read(0)
            if (txs | rxs) & 0x70 or state & 0xff0006:
                raise RuntimeError('DMA/PL fault; reload overlay')
            if txs & 0x1000 and rxs & 0x1000:
                break
            if time.monotonic()-started > timeout:
                raise TimeoutError('DMA timeout; reload overlay before releasing buffers')
            time.sleep(0.001)
        self.rx.invalidate()
        elapsed = time.monotonic()-started
        result = decode_result(self.rx.tobytes(), transaction_id)
        for unit in result:
            expected = {i:(p,s) for p,s,i in jobs[12*unit['unit']:12*(unit['unit']+1)]}
            if {i for i,_ in unit['records']} != set(expected):
                raise ValueError('Result ID set mismatch')
            if verify:
                for i,raw in unit['records']:
                    if raw != digest(*expected[i]):
                        raise ValueError('MD5crypt result mismatch')
        self.poisoned = False
        return {'units':result, 'dma_seconds':elapsed, 'software_verified':verify}
