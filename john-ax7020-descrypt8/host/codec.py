"""Version 1 fixed-batch DMA ABI; intentionally NOT the John USB packet ABI."""
import struct

ALPHABET = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'

def target_parameters(target):
    if len(target) != 13 or any(c not in ALPHABET for c in target):
        raise ValueError('Expected a traditional 13-character DES-crypt hash')
    if ALPHABET.index(target[-1]) & 3:
        raise ValueError('Noncanonical hash padding')
    salt = ALPHABET.index(target[0]) | ALPHABET.index(target[1]) << 6
    # crypt base64 is MSB-first; upstream FPGA IP1 exposes reversed bit order.
    encoded = 0
    for c in target[2:]:
        encoded = encoded << 6 | ALPHABET.index(c)
    binary = encoded >> 2
    reversed_bits = int(format(binary, '064b')[::-1], 2)
    return salt, reversed_bits & ((1 << 35) - 1)

def encode_batch(candidates, target):
    if len(candidates) != 16:
        raise ValueError('Exactly 16 candidates required; split/pad on host explicitly')
    salt, low35 = target_parameters(target)
    result = struct.pack('<4I', 0x31534344, salt, low35 & 0xffffffff, low35 >> 32)
    for word in candidates:
        raw = word.encode('ascii')
        if len(raw) > 8 or b'\0' in raw:
            raise ValueError('Use 0..8 ASCII bytes without embedded NUL')
        result += raw.ljust(8, b'\0')
    return result

def decode_result(data):
    if len(data) != 16:
        raise ValueError('Expected 16-byte response')
    magic, mask, cycles, status = struct.unpack('<4I', data)
    if magic != 0x31524344 or mask >> 16 or status >> 24 != 0xdc or status & 0x1fe:
        raise ValueError('Invalid or faulted hardware response')
    return {'provisional_mask': mask, 'compute_cycles': cycles, 'status': status}

def verify_matches(candidates, target, mask):
    # Partial hardware matches are never accepted without full verification.
    from passlib.hash import des_crypt
    return [i for i, word in enumerate(candidates)
            if mask & (1 << i) and des_crypt.verify(word, target)]
