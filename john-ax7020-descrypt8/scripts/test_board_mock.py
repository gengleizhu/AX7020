"""Software-only register-order/timeout tests, not evidence of physical DMA."""
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from pynq_demo import DescryptDevice

class Buffer:
    def __init__(self,address):self.physical_address=address;self.data=[0]*4
    def __setitem__(self,key,value):self.data=list(value) if not isinstance(value,int) else [value]*4
    def flush(self):pass
    def invalidate(self):pass
    def tobytes(self):return struct.pack('<%dI'%len(self.data),*self.data)
class NumpyStub:
    @staticmethod
    def frombuffer(payload,dtype):return struct.unpack('<290I',payload)
class Status:
    def read(self,offset):return 0xd8000000
class DMA:
    def __init__(self,rx,mode):self.rx=rx;self.mode=mode;self.events=[];self.finished=False
    def write(self,offset,value):
        self.events.append((offset,value))
        if offset==0x28:
            assert (0x58,168) in self.events,'RX must be armed first'
            self.finished=True
            self.rx.data=[0x38524344,42]+[x for i in range(8) for x in [i,0x31524344,0xffff,562,0xdc000001]]
    def read(self,offset):
        if self.mode=='error':return 0x10
        if self.mode=='timeout':return 0
        return 0x1002 if self.finished else 0
def device(mode):
    dev=DescryptDevice.__new__(DescryptDevice)
    dev._np=NumpyStub();dev.tx=Buffer(0x10000);dev.rx=Buffer(0x20000)
    dev.dma=DMA(dev.rx,mode);dev.status=Status();dev.poisoned=False
    return dev
class BoardMockTests(unittest.TestCase):
    def test_success(self):
        dev=device('ok')
        result=dev.compute([['mypwd123']*16]*8,['55hMnVAwQjWXI']*8,42)
        self.assertEqual(result['cores'][7]['verified_indices'],list(range(16)))
        self.assertFalse(dev.poisoned)
    def test_dma_error(self):
        dev=device('error')
        with self.assertRaises(RuntimeError):dev.compute([['mypwd123']*16]*8,['55hMnVAwQjWXI']*8,42)
        self.assertTrue(dev.poisoned)
        with self.assertRaises(RuntimeError):dev.compute([['mypwd123']*16]*8,['55hMnVAwQjWXI']*8,42)
    def test_timeout(self):
        dev=device('timeout')
        with self.assertRaises(TimeoutError):dev.compute([['mypwd123']*16]*8,['55hMnVAwQjWXI']*8,42,timeout=0)
        self.assertTrue(dev.poisoned)
        self.assertIsNotNone(dev.rx)
if __name__=='__main__':unittest.main()
