"""Host protocol and independent SHA512-crypt reference for the 4-unit design."""
import hashlib
import struct

REQUEST_MAGIC = 0x34534853   # "SHS4" in the byte stream
RESPONSE_MAGIC = 0x34524853  # "SHR4"
UNIT_MAGIC = 0x3453484A      # "JHS4"
UNITS = 4
JOBS_PER_UNIT = 16

def digest(password: bytes, salt: bytes, rounds: int = 5000) -> bytes:
    """Return the canonical 64-byte SHA512-crypt intermediate digest."""
    if not isinstance(password, bytes) or len(password) > 64 or b'\0' in password:
        raise ValueError('Password must be 0..64 bytes, no NUL')
    if not isinstance(salt, bytes) or not 1 <= len(salt) <= 16 or b'\0' in salt or b'$' in salt:
        raise ValueError('Salt must be 1..16 bytes, no NUL or dollar sign')
    if not isinstance(rounds, int) or not 1 <= rounds <= 999_999_999:
        raise ValueError('Rounds must be 1..999999999 for reference/test calculation')

    alt = hashlib.sha512(password + salt + password).digest()
    data = password + salt + (alt * ((len(password) + 63) // 64))[:len(password)]
    count = len(password)
    while count:
        data += alt if count & 1 else password
        count >>= 1
    value = hashlib.sha512(data).digest()

    p_digest = hashlib.sha512(password * len(password)).digest()
    p_bytes = (p_digest * ((len(password) + 63) // 64))[:len(password)]
    s_digest = hashlib.sha512(salt * (16 + value[0])).digest()
    s_bytes = (s_digest * ((len(salt) + 63) // 64))[:len(salt)]

    for index in range(rounds):
        data = p_bytes if index & 1 else value
        if index % 3:
            data += s_bytes
        if index % 7:
            data += p_bytes
        data += value if index & 1 else p_bytes
        value = hashlib.sha512(data).digest()
    return value

_CRYPT64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_SHA512_GROUPS = ((0,21,42,4),(22,43,1,4),(44,2,23,4),(3,24,45,4),
                  (25,46,4,4),(47,5,26,4),(6,27,48,4),(28,49,7,4),
                  (50,8,29,4),(9,30,51,4),(31,52,10,4),(53,11,32,4),
                  (12,33,54,4),(34,55,13,4),(56,14,35,4),(15,36,57,4),
                  (37,58,16,4),(59,17,38,4),(18,39,60,4),(40,61,19,4),
                  (62,20,41,4),(-1,-1,63,2))

def crypt_checksum(raw: bytes) -> str:
    if len(raw) != 64:
        raise ValueError('Raw digest must be 64 bytes')
    out = ''
    for a, b, c, count in _SHA512_GROUPS:
        value = ((0 if a < 0 else raw[a]) << 16) | ((0 if b < 0 else raw[b]) << 8) | raw[c]
        for _ in range(count):
            out += _CRYPT64[value & 63]
            value >>= 6
    return out

def crypt_string(password: bytes, salt: bytes, rounds: int = 5000) -> str:
    prefix = '$6$' if rounds == 5000 else f'$6$rounds={rounds}$'
    return prefix + salt.decode('ascii') + '$' + crypt_checksum(digest(password, salt, rounds))

def hardware_words(raw: bytes):
    """Map canonical SHA bytes to the original John's UOB 32-bit words."""
    if len(raw) != 64:
        raise ValueError('Raw digest must be 64 bytes')
    return struct.unpack('<16I', raw)

def encode_job(password: bytes, salt: bytes, job_id: int, rounds: int = 5000) -> bytes:
    if not isinstance(password, bytes) or len(password) > 64 or b'\0' in password:
        raise ValueError('Password must be 0..64 bytes, no NUL')
    if not isinstance(salt, bytes) or not 1 <= len(salt) <= 16 or b'\0' in salt or b'$' in salt:
        raise ValueError('Salt must be 1..16 bytes, no NUL or dollar sign')
    if not isinstance(rounds, int) or not 1000 <= rounds <= 999_999_999:
        raise ValueError('Rounds must be 1000..999999999')
    if not isinstance(job_id, int) or not 0 <= job_id < 2**64:
        raise ValueError('Job ID must be uint64')
    return (struct.pack('<2I', rounds, len(salt)) + salt.ljust(16, b'\0') +
            struct.pack('<Q2I', job_id, len(password), 0) + password.ljust(64, b'\0'))

def encode_batch(jobs, transaction_id: int) -> bytes:
    if not isinstance(transaction_id, int) or not 0 <= transaction_id < 2**32:
        raise ValueError('Transaction ID must be uint32')
    if len(jobs) != UNITS * JOBS_PER_UNIT or len({job[2] for job in jobs}) != 64:
        raise ValueError('Exactly 64 unique job IDs are required')
    frames = []
    for job in jobs:
        frames.append(encode_job(*job))
    return struct.pack('<2I', REQUEST_MAGIC, transaction_id) + b''.join(frames)

def decode_result(data: bytes, transaction_id: int):
    if len(data) != 4664:
        raise ValueError('Expected 4664 response bytes')
    if struct.unpack_from('<2I', data) != (RESPONSE_MAGIC, transaction_id):
        raise ValueError('Header or transaction mismatch')
    result, ids = [], set()
    for unit_index in range(UNITS):
        offset = 8 + unit_index * 1164
        unit, magic, cycles = struct.unpack_from('<3I', data, offset)
        if unit != unit_index or magic != UNIT_MAGIC:
            raise ValueError('Unit or unit-header mismatch')
        records = []
        for record_index in range(JOBS_PER_UNIT):
            start = offset + 12 + record_index * 72
            job_id = struct.unpack_from('<Q', data, start)[0]
            if job_id in ids:
                raise ValueError('Duplicate result ID')
            ids.add(job_id)
            records.append((job_id, data[start + 8:start + 72]))
        result.append({'unit': unit_index, 'cycles': cycles, 'records': records})
    return result
