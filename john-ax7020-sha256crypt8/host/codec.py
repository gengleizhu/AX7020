"""Host protocol and independent SHA256-crypt reference for the 8-unit design."""
import hashlib
import struct

REQUEST_MAGIC = 0x38534853   # "SHS8" in the byte stream
RESPONSE_MAGIC = 0x38524853  # "SHR8"
UNIT_MAGIC = 0x3853484A      # "JHS8"
UNITS = 8
JOBS_PER_UNIT = 12

def digest(password: bytes, salt: bytes, rounds: int = 5000) -> bytes:
    """Return the canonical 32-byte SHA256-crypt intermediate digest."""
    if not isinstance(password, bytes) or len(password) > 32 or b'\0' in password:
        raise ValueError('Password must be 0..32 bytes, no NUL')
    if not isinstance(salt, bytes) or not 1 <= len(salt) <= 16 or b'\0' in salt or b'$' in salt:
        raise ValueError('Salt must be 1..16 bytes, no NUL or dollar sign')
    if not isinstance(rounds, int) or not 1 <= rounds <= 999_999_999:
        raise ValueError('Rounds must be 1..999999999 for reference/test calculation')

    alt = hashlib.sha256(password + salt + password).digest()
    data = password + salt + (alt * ((len(password) + 31) // 32))[:len(password)]
    count = len(password)
    while count:
        data += alt if count & 1 else password
        count >>= 1
    value = hashlib.sha256(data).digest()

    p_digest = hashlib.sha256(password * len(password)).digest()
    p_bytes = (p_digest * ((len(password) + 31) // 32))[:len(password)]
    s_digest = hashlib.sha256(salt * (16 + value[0])).digest()
    s_bytes = (s_digest * ((len(salt) + 31) // 32))[:len(salt)]

    for index in range(rounds):
        data = p_bytes if index & 1 else value
        if index % 3:
            data += s_bytes
        if index % 7:
            data += p_bytes
        data += value if index & 1 else p_bytes
        value = hashlib.sha256(data).digest()
    return value

_CRYPT64 = './0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
_SHA256_GROUPS = ((0,10,20,4),(21,1,11,4),(12,22,2,4),(3,13,23,4),
                  (24,4,14,4),(15,25,5,4),(6,16,26,4),(27,7,17,4),
                  (18,28,8,4),(9,19,29,4),(-1,31,30,3))

def crypt_checksum(raw: bytes) -> str:
    if len(raw) != 32:
        raise ValueError('Raw digest must be 32 bytes')
    out = ''
    for a, b, c, count in _SHA256_GROUPS:
        value = ((0 if a < 0 else raw[a]) << 16) | (raw[b] << 8) | raw[c]
        for _ in range(count):
            out += _CRYPT64[value & 63]
            value >>= 6
    return out

def crypt_string(password: bytes, salt: bytes, rounds: int = 5000) -> str:
    prefix = '$5$' if rounds == 5000 else f'$5$rounds={rounds}$'
    return prefix + salt.decode('ascii') + '$' + crypt_checksum(digest(password, salt, rounds))

def hardware_words(raw: bytes):
    """Map canonical SHA bytes to the original John's UOB 32-bit words."""
    if len(raw) != 32:
        raise ValueError('Raw digest must be 32 bytes')
    return struct.unpack('<8I', raw)

def encode_job(password: bytes, salt: bytes, job_id: int, rounds: int = 5000) -> bytes:
    if not isinstance(password, bytes) or len(password) > 32 or b'\0' in password:
        raise ValueError('Password must be 0..32 bytes, no NUL')
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
    if len(jobs) != UNITS * JOBS_PER_UNIT or len({job[2] for job in jobs}) != 96:
        raise ValueError('Exactly 96 unique job IDs are required')
    frames = []
    for job in jobs:
        frames.append(encode_job(*job))
    return struct.pack('<2I', REQUEST_MAGIC, transaction_id) + b''.join(frames)

def decode_result(data: bytes, transaction_id: int):
    if len(data) != 3944:
        raise ValueError('Expected 3944 response bytes')
    if struct.unpack_from('<2I', data) != (RESPONSE_MAGIC, transaction_id):
        raise ValueError('Header or transaction mismatch')
    result, ids = [], set()
    for unit_index in range(UNITS):
        offset = 8 + unit_index * 492
        unit, magic, cycles = struct.unpack_from('<3I', data, offset)
        if unit != unit_index or magic != UNIT_MAGIC:
            raise ValueError('Unit or unit-header mismatch')
        records = []
        for record_index in range(JOBS_PER_UNIT):
            start = offset + 12 + record_index * 40
            job_id = struct.unpack_from('<Q', data, start)[0]
            if job_id in ids:
                raise ValueError('Duplicate result ID')
            ids.add(job_id)
            records.append((job_id, data[start + 8:start + 40]))
        result.append({'unit': unit_index, 'cycles': cycles, 'records': records})
    return result
