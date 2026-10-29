"""AXI ABI 1.1 / DMA ABI 1.0. Transport-independent PS control helpers.

Native payload encoders/decoders remain algorithm-specific. This module does
not program physical DMA addresses or make Python buffers DMA-coherent.
"""
from dataclasses import dataclass
import struct

BASE = 0x43C00000
REGISTER_ABI = 0x10001
STREAM_ABI = 0x10000
NAMES = {1: 'bcrypt', 2: 'descrypt', 3: 'md5crypt', 4: 'sha256crypt', 5: 'sha512crypt'}
# physical slots, native request bytes, native response bytes
LAYOUT = {2: (128, 1160, 168), 3: (96, 9992, 2408),
          4: (96, 9992, 3944), 5: (64, 6664, 4664)}
MAGIC = {2: (0x38534344, 0x38524344), 3: (0x38534D44, 0x38524D44),
         4: (0x38534853, 0x38524853), 5: (0x34534853, 0x34524853)}


@dataclass(frozen=True)
class Batch:
    algorithm: int
    task: int
    shard: int
    batch: int
    valid_count: int
    physical_count: int
    payload: bytes
    last_batch: bool = False

    def validate(self):
        if self.algorithm not in NAMES:
            raise ValueError('unknown algorithm')
        for name, value, limit in [('task', self.task, 1 << 64),
                                   ('shard', self.shard, 1 << 32),
                                   ('batch', self.batch, 1 << 32)]:
            if not isinstance(value, int) or not 0 <= value < limit:
                raise ValueError(name + ' out of range')
        if not 0 < self.valid_count <= self.physical_count:
            raise ValueError('invalid candidate counts')
        if self.algorithm == 1:
            if self.physical_count != self.valid_count or self.physical_count > 170:
                raise ValueError('bcrypt requires 1..170 finite, unpadded results')
            if not 0 < len(self.payload) <= 65536:
                raise ValueError('bcrypt native packet length')
            # John packet checksum/config/candidate semantics require its codec.
        else:
            slots, length, _ = LAYOUT[self.algorithm]
            if self.physical_count != slots or len(self.payload) != length:
                raise ValueError('native batch size')
            if struct.unpack_from('<II', self.payload) != (MAGIC[self.algorithm][0], self.batch):
                raise ValueError('native request magic/tag')
        return self

    @property
    def output_bytes(self):
        return 48 * self.physical_count if self.algorithm == 1 else LAYOUT[self.algorithm][2]

    def descriptor(self):
        self.validate()
        return [self.task & 0xFFFFFFFF, self.task >> 32, self.shard, self.batch,
                self.algorithm, 0x100 + self.algorithm, len(self.payload),
                64 + self.output_bytes, self.valid_count, self.physical_count,
                self.output_bytes, int(self.last_batch), 0, 0, 0, 0, 0, 0]

    def request(self):
        d = self.descriptor()
        h = [0x3151544A, STREAM_ABI, 64, 64 + len(self.payload),
             self.algorithm, 0x100 + self.algorithm, *d[:4],
             self.valid_count, self.physical_count, self.output_bytes,
             int(self.last_batch), 0, 0]
        return struct.pack('<16I', *h) + self.payload

    def parse_response(self, data):
        self.validate()
        if len(data) < 64:
            raise ValueError('truncated response')
        h = struct.unpack_from('<16I', data)
        if h[:3] != (0x3152544A, STREAM_ABI, 64) or h[3] != len(data):
            raise ValueError('response header/length')
        expected = (self.algorithm, 0x100 + self.algorithm, self.task & 0xFFFFFFFF,
                    self.task >> 32, self.shard, self.batch)
        if h[4:10] != expected:
            raise ValueError('response belongs to another batch')
        flags = (1 if self.algorithm == 2 else 0) | (2 if self.valid_count < self.physical_count else 0)
        if h[14] != flags or h[15] != 0:
            raise ValueError('response flags/reserved')
        if h[10]:
            if len(data) != 64 or any(h[11:14]):
                raise ValueError('malformed error response')
            raise RuntimeError('PL batch error code=%d; inspect ERROR_DETAIL and NEED_RELOAD' % h[10])
        records = 8 if self.algorithm == 2 else self.physical_count
        if h[11:14] != (self.valid_count, self.output_bytes, records) or len(data) != 64 + self.output_bytes:
            raise ValueError('result count/length mismatch')
        payload = data[64:]
        if self.algorithm != 1 and struct.unpack_from('<II', payload) != (MAGIC[self.algorithm][1], self.batch):
            raise ValueError('native response magic/tag')
        # Caller must validate all native unit/job IDs, drop padded job IDs,
        # and FULLY verify DES provisional matches against the target.
        return payload


class Registers:
    """Callbacks read32(offset), write32(offset, value), already mapped to BASE."""
    def __init__(self, read32, write32):
        self.read = read32
        self.write = write32
        self.sequence = read32(0x088)

    def identify(self):
        if self.read(0) != 0x4A435250 or self.read(4) != REGISTER_ABI:
            raise RuntimeError('incompatible bitstream/register ABI')
        return dict(algorithm=self.read(0x020), units=self.read(0x024),
                    cores_per_unit=self.read(0x028), capabilities=self.read(0x030))

    def command(self, command):
        self.sequence = (self.sequence + 1) & 0xFFFFFFFF
        self.write(0x088, self.sequence)
        self.write(0x080, command)
        if self.read(0x08C) != self.sequence:
            raise RuntimeError('command acknowledgement mismatch')
        result = self.read(0x090)
        if result:
            raise RuntimeError('command rejected: %d' % result)

    def arm(self, batch):
        info = self.identify()
        words = batch.descriptor()
        if info['algorithm'] != batch.algorithm or not self.read(0x084) & 1:
            raise RuntimeError('wrong algorithm or PL not ready')
        for i, word in enumerate(words):
            self.write(0x100 + 4 * i, word)
        self.command(1)

    def snapshot(self):
        self.command(4)
        seq = self.read(0x0AC)
        words = [self.read(0x180 + 4 * i) for i in range(30)]
        if self.read(0x0AC) != seq:
            raise RuntimeError('concurrent snapshot: serialize register access')
        return dict(sequence=seq, completed=words[2] | (words[3] << 32),
                    total=words[28], elapsed_cycles=words[10] | (words[11] << 32),
                    task=words[24] | (words[25] << 32), shard=words[26],
                    batch=words[23], status=words[27])

    def release(self):
        # Caller must first confirm both DMA channels have stopped and buffers
        # were synchronized for CPU access. Do NOT reset native cores here.
        self.command(2)
