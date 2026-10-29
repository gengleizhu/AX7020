"""离线软件测试：不把Mock DMA当作硬件验收。"""
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/"host"),str(ROOT/"board")]
from sim_udp_transport import Frame, Assembly, DATA
from john_packet_codec import Decoder
from dma_benchmark import DmaBatch


class Buffer(bytearray):
    next_addr=4096
    def __init__(self,size):
        super().__init__(size)
        self.physical_address=Buffer.next_addr
        Buffer.next_addr+=4096
        self.freed=False
    def flush(self): pass
    def invalidate(self): pass
    def freebuffer(self): self.freed=True


class FakeHardware:
    def __init__(self,packets):
        self.buffers={}
        self.packets=list(packets)
        self.writes=[]
        self.regs={4:2,0x34:2,0x58:48}
        self.started=False
    def cma_array(self,shape,dtype):
        b=Buffer(shape[0]); self.buffers[b.physical_address]=b
        return b
    def read(self,addr): return self.regs.get(addr,0)
    def write(self,addr,value):
        self.writes.append((addr,value)); self.regs[addr]=value
        if addr==0x28: self.started=True
        if self.started and addr in (0x28,0x58) and self.packets:
            self.buffers[self.regs[0x48]][:]=self.packets.pop(0)


class IntegrationTest(unittest.TestCase):
    def test_crc_header_and_payload(self):
        raw=Frame(DATA,1,2,0,1,3,b"abc").encode()
        self.assertEqual(Frame.decode(raw).payload,b"abc")
        for i in range(len(raw)):
            changed=bytearray(raw); changed[i]^=1
            with self.assertRaises(ValueError): Frame.decode(changed)

    def test_reassembly(self):
        a=Frame(DATA,1,2,0,2,5,b"ab")
        b=Frame(DATA,1,2,1,2,5,b"cde")
        assembly=Assembly(b)
        assembly.add(b); assembly.add(b)
        self.assertEqual(assembly.missing(),[0])
        with self.assertRaises(ValueError): assembly.finish()
        assembly.add(a)
        self.assertEqual(assembly.finish(),b"abcde")
        with self.assertRaises(ValueError):
            assembly.add(Frame(DATA,1,2,0,2,5,b"zz"))
        with self.assertRaises(ValueError):
            assembly.add(Frame(DATA,99,2,0,2,5,b"ab"))

    def test_dma_schedule_mock_only(self):
        source=ROOT/"sim/integration/cost4"
        expected=[bytes.fromhex(p) for p in json.loads((source/"expected.json").read_text())]
        hw=FakeHardware(expected)
        driver=DmaBatch(hw,hw,lambda:0xbc000000)
        result=driver.run((source/"input.bin").read_bytes(),32)
        self.assertEqual(result,b"".join(expected))
        addresses=[a for a,_ in hw.writes]
        self.assertLess(addresses.index(0x58),addresses.index(0x28))
        self.assertEqual(addresses.count(0x58),32)
        self.assertTrue(all(b.freed for b in hw.buffers.values()))

    def test_dma_timeout_preserves_memory(self):
        source=ROOT/"sim/integration/cost4"
        hw=FakeHardware([])
        hw.regs[0x34]=0
        driver=DmaBatch(hw,hw,lambda:0xbc000000,timeout=.002)
        with self.assertRaises(TimeoutError):
            driver.run((source/"input.bin").read_bytes(),32)
        self.assertTrue(driver.poisoned)
        self.assertTrue(all(not b.freed for b in hw.buffers.values()))


if __name__=="__main__":
    unittest.main(testRunner=unittest.TextTestRunner(stream=sys.stdout,verbosity=2))
