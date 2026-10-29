"""PYNQ 2.4板上验收入口；当前仅离线单元测试，未实板运行。

本程序只从DMA读取结果，不调用CPU bcrypt。需要本工程bit/hwh和host目录。
为了有限超时和明确错误处理，直接使用DMA MMIO寄存器及Xlnk连续内存。
"""
import argparse
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "host"))
from john_packet_codec import Decoder


class DmaBatch:
    def __init__(self, mmio, allocator, read_status, timeout=30):
        self.mmio, self.allocator, self.read_status = mmio, allocator, read_status
        self.timeout = timeout
        self.poisoned = False
        self.retained = []

    def check(self, deadline):
        if time.monotonic() >= deadline:
            raise TimeoutError("DMA timeout; reload trusted overlay before retry")
        status = self.read_status()
        if status >> 24 != 0xbc or status & 0xffffff:
            raise RuntimeError("PL status 0x{:08x}".format(status))
        for offset in (4, 0x34):
            value = self.mmio.read(offset)
            if value & 0x70:
                raise RuntimeError("DMA error offset=0x{:x} status=0x{:x}".format(offset, value))

    def run(self, raw, count):
        if self.poisoned:
            raise RuntimeError("session requires overlay reload")
        decoder = Decoder()
        packets = decoder.feed(raw)
        if decoder.buffer or [p.type for p in packets] != [3,2,1] or not 1<=count<=65535:
            raise ValueError("expected one complete dictionary batch")
        cfg = packets[0].payload
        if len(cfg)!=24 or cfg[16] not in b"abxy" or cfg[-3:]!=b"\0\0\xcc":
            raise ValueError("invalid config")
        iterations = int.from_bytes(cfg[17:21], "little")
        if iterations<16 or iterations>2**20 or iterations & (iterations-1):
            raise ValueError("invalid iterations")
        if packets[1].payload != b"\0"*5+b"\xbb":
            raise ValueError("dictionary mode required")
        words = packets[2].payload.split(b"\0")
        if words[-1] or len(words)-1 != count or any(len(w)>71 for w in words[:-1]):
            raise ValueError("word count/encoding; this entry supports terminated words <=71 bytes")
        if len(raw)>=2**23:
            raise ValueError("DMA length")
        tx = self.allocator.cma_array(shape=(len(raw),), dtype="uint8")
        rx = self.allocator.cma_array(shape=(48,), dtype="uint8")
        self.retained = [tx,rx]
        deadline = time.monotonic()+self.timeout
        result = bytearray()
        seen = set()
        try:
            tx[:] = list(raw)
            tx.flush()
            self.check(deadline)
            # 新加载overlay的DMA处于停止状态。重复批次保留原核心状态，不做伪软复位。
            self.mmio.write(0x00,1)
            self.mmio.write(0x30,1)
            while self.mmio.read(4)&1 or self.mmio.read(0x34)&1:
                self.check(deadline)
                time.sleep(.0001)
            for i in range(count):
                # 每一个TLAST对应48字节D3包；不能用一次大接收去等待32个TLAST。
                self.mmio.write(0x48,rx.physical_address)
                self.mmio.write(0x58,48)
                if i==0:
                    self.mmio.write(0x18,tx.physical_address)
                    self.mmio.write(0x28,len(raw))
                while not self.mmio.read(0x34)&2:
                    self.check(deadline)
                    time.sleep(.0001)
                self.check(deadline)
                if self.mmio.read(0x58)!=48:
                    raise RuntimeError("unexpected S2MM byte count")
                rx.invalidate()
                packet_raw = bytes(rx)
                decoded = Decoder().feed(packet_raw)
                if len(decoded)!=1 or decoded[0].type!=0xd3 or len(decoded[0].payload)!=30:
                    raise RuntimeError("invalid DMA John result")
                packet = decoded[0]
                word_id = int.from_bytes(packet.payload[:2], "little")
                gen_id = int.from_bytes(packet.payload[2:6], "little")
                if packet.id!=packets[1].id or gen_id!=0 or word_id>=count or word_id in seen:
                    raise RuntimeError("result identity mismatch")
                seen.add(word_id)
                result.extend(packet_raw)
            while not self.mmio.read(4)&2:
                self.check(deadline)
                time.sleep(.0001)
            for buffer in self.retained:
                buffer.freebuffer()
            self.retained=[]
            return bytes(result)
        except Exception:
            self.poisoned=True
            # 不释放可能仍被DMA访问的CMA内存；调用方须先重配置/确认DMA停止。
            self.mmio.write(0,0)
            self.mmio.write(0x30,0)
            raise


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--bit",required=True)
    p.add_argument("--input",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--count",type=int,default=32)
    p.add_argument("--timeout",type=float,default=30)
    args=p.parse_args()
    from pynq import Overlay, Xlnk
    overlay=Overlay(args.bit)
    # 此处bitstream加载是本地管理员操作，不暴露网络加载接口。
    driver=DmaBatch(overlay.dma.mmio,Xlnk(),lambda:overlay.status.read(0),args.timeout)
    start=time.monotonic()
    raw=driver.run(args.input.read_bytes(),args.count)
    args.output.write_bytes(raw)
    print("DMA_RESULTS count={} elapsed_seconds={:.6f}".format(args.count,time.monotonic()-start))


if __name__=="__main__":
    main()
