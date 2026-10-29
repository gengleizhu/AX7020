"""Host control-flow tests, NOT hardware/DMA verification."""
import struct
import unittest
from types import SimpleNamespace
from codec import digest
from pynq_demo import Md5cryptDevice

class Buffer:
    physical_address=0x100000
    def __init__(self,data=b''):self.data=data
    def __setitem__(self,key,value):pass
    def flush(self):pass
    def invalidate(self):pass
    def tobytes(self):return self.data

class Registers:
    def __init__(self,value):self.value=value;self.writes=[]
    def read(self,offset):return self.value
    def write(self,offset,value):self.writes.append((offset,value))

def device(error=False):
    obj=Md5cryptDevice.__new__(Md5cryptDevice)
    obj.np=SimpleNamespace(frombuffer=lambda data,dtype:data)
    obj.poisoned=False;obj.status=Registers(0xa8000000)
    obj.dma=Registers(0x10 if error else 0x1000)
    obj.tx=Buffer()
    packet=struct.pack('<2I',0x38524d44,1)
    for u in range(8):
        packet+=struct.pack('<3I',u,0x38524d4a,10000)
        packet+=b''.join(struct.pack('<Q',u*12+j)+digest(b'abc',b'a') for j in range(12))
    obj.rx=Buffer(packet)
    return obj

class HostTests(unittest.TestCase):
    jobs=[(b'abc',b'a',i) for i in range(96)]
    def test_success(self):
        d=device();r=d.compute(self.jobs,1)
        self.assertTrue(r['software_verified']);self.assertFalse(d.poisoned)
        self.assertLess(d.dma.writes.index((0x58,2408)),d.dma.writes.index((0x28,9992)))
    def test_error_poison(self):
        d=device(True)
        with self.assertRaises(RuntimeError):d.compute(self.jobs,1)
        self.assertTrue(d.poisoned)
        with self.assertRaises(RuntimeError):d.compute(self.jobs,1)
    def test_bad_id_set(self):
        d=device();bad=list(self.jobs);bad[0]=(b'abc',b'a',100)
        with self.assertRaises(ValueError):d.compute(bad,1)
        self.assertTrue(d.poisoned)

if __name__=='__main__':unittest.main()
