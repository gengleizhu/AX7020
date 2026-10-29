import struct, unittest
from types import SimpleNamespace
from codec import digest, hardware_words
from pynq_demo import Sha512cryptDevice

class Buffer:
    physical_address=0x100000
    def __init__(self,data=b''): self.data=data
    def __setitem__(self,key,value): pass
    def flush(self): pass
    def invalidate(self): pass
    def tobytes(self): return self.data
class Registers:
    def __init__(self,value): self.value=value; self.writes=[]
    def read(self,offset): return self.value
    def write(self,offset,value): self.writes.append((offset,value))

def device(error=False):
    obj=Sha512cryptDevice.__new__(Sha512cryptDevice)
    obj.np=SimpleNamespace(frombuffer=lambda data,dtype:data); obj.poisoned=False
    obj.status=Registers(0xa5000000); obj.dma=Registers(0x10 if error else 0x1000); obj.tx=Buffer()
    words=[0x34524853,1]
    raw=digest(b'abc',b'a',1000)
    for unit in range(4):
        words += [unit,0x3453484a,10000]
        for slot in range(16): words += [unit*16+slot,0] + list(hardware_words(raw))
    obj.rx=Buffer(struct.pack('<1166I',*words)); return obj

class HostTests(unittest.TestCase):
    jobs=[(b'abc',b'a',i,1000) for i in range(64)]
    def test_success(self):
        dev=device(); result=dev.compute(self.jobs,1)
        self.assertTrue(result['software_verified']); self.assertFalse(dev.poisoned)
        self.assertLess(dev.dma.writes.index((0x58,4664)),dev.dma.writes.index((0x28,6664)))
    def test_error_poison(self):
        dev=device(True)
        with self.assertRaises(RuntimeError): dev.compute(self.jobs,1)
        self.assertTrue(dev.poisoned)

if __name__ == '__main__': unittest.main()
