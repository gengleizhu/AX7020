"""PYNQ 2.4 DMA helper. Not board-tested; reload overlay after any exception."""
import time
from codec import encode_batch, decode_result, digest

class Sha256cryptDevice:
    def __init__(self, overlay):
        from pynq import Xlnk, MMIO
        import numpy as np
        self.np, self.overlay = np, overlay
        self.dma = MMIO(overlay.ip_dict['dma']['phys_addr'], 0x1000)
        self.status = MMIO(overlay.ip_dict['status']['phys_addr'], 0x1000)
        self.allocator = Xlnk()
        self.tx = self.allocator.cma_array(shape=(2498,), dtype=np.uint32)
        self.rx = self.allocator.cma_array(shape=(986,), dtype=np.uint32)
        self.poisoned = False
        self.dma.write(0x00, 1); self.dma.write(0x30, 1)

    def compute(self, jobs, transaction_id, timeout=60.0, verify=True):
        if self.poisoned:
            raise RuntimeError('Reload overlay after failed session; buffers retained')
        payload = encode_batch(jobs, transaction_id)
        if self.status.read(0) != 0xa6000000:
            raise RuntimeError('PL not idle/healthy')
        self.tx[:] = self.np.frombuffer(payload, dtype='<u4'); self.tx.flush()
        self.rx[:] = 0; self.rx.flush(); self.poisoned = True
        started = time.monotonic()
        self.dma.write(0x34, 0x7000); self.dma.write(0x04, 0x7000)
        self.dma.write(0x48, self.rx.physical_address); self.dma.write(0x58, 3944)
        self.dma.write(0x18, self.tx.physical_address); self.dma.write(0x28, 9992)
        while True:
            txs, rxs, state = self.dma.read(0x04), self.dma.read(0x34), self.status.read(0)
            if (txs | rxs) & 0x70 or state & 0x00ff0006:
                raise RuntimeError('DMA/PL fault; reload overlay')
            if txs & 0x1000 and rxs & 0x1000: break
            if time.monotonic() - started > timeout:
                raise TimeoutError('DMA timeout; reload overlay')
            time.sleep(0.001)
        self.rx.invalidate()
        result = decode_result(self.rx.tobytes(), transaction_id)
        if verify:
            for unit in result:
                expected = {j[2]: j for j in jobs[12*unit['unit']:12*(unit['unit']+1)]}
                if {job_id for job_id, _ in unit['records']} != set(expected):
                    raise ValueError('Result ID set mismatch')
                for job_id, raw in unit['records']:
                    job = expected[job_id]
                    password, salt, rounds = job[0], job[1], job[3] if len(job) == 4 else 5000
                    if raw != digest(password, salt, rounds):
                        raise ValueError('SHA256crypt result mismatch')
        self.poisoned = False
        return {'units': result, 'dma_seconds': time.monotonic()-started,
                'software_verified': verify}
