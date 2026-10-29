import json, struct, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from codec import crypt_string, digest, encode_batch, hardware_words
from passlib.hash import sha256_crypt

lengths = [0,1,2,3,7,8,12,15,16,24,31,32]
salts = [b'.', b'a', b'ab', b'12345678', b'./Az09', b'0123456789abcdef', b'55', b'XYZ']
jobs = []
for unit in range(8):
    for slot, length in enumerate(lengths):
        password = bytes(33 + (unit * 13 + slot * 7 + k) % 90 for k in range(length))
        salt = salts[unit]
        job_id = unit * 12 + slot
        jobs.append((password, salt, job_id, 10))

assert crypt_string(b'Hello world!', b'saltstring', 5000) == \
       '$5$saltstring$5B8vYYiY.CVt1RlTTf8KbXBH3hsxY/GNooZaBBGWEc5'
def test_packet(job):
    password,salt,job_id,rounds=job
    return (struct.pack('<2I',rounds,len(salt))+salt.ljust(16,b'\0')+
            struct.pack('<Q2I',job_id,len(password),0)+password.ljust(64,b'\0'))
frame = struct.pack('<2I',0x38534853,0x12345678)+b''.join(test_packet(job) for job in jobs)
(ROOT / 'sim/input.mem').write_text('\n'.join(f'{word:08x}' for word in struct.unpack('<2498I', frame)) + '\n')
(ROOT / 'sim/expected.mem').write_text('\n'.join(
    f'{word:08x}' for password, salt, _, rounds in jobs
    for word in hardware_words(digest(password, salt, rounds))) + '\n')
(ROOT / 'sim/vectors.json').write_text(json.dumps([
    {'id': job_id, 'password_hex': password.hex(), 'salt': salt.decode(),
     'rounds': rounds, 'digest': digest(password, salt, rounds).hex()}
    for password, salt, job_id, rounds in jobs], indent=2))
print('REFERENCE_PASS parallel_jobs=96 parallel_rounds=10 standard_unit_jobs=12 standard_rounds=1000 default_5000_vector=pass')

known_jobs=[(bytes(33+(slot*7+k)%90 for k in range(length)),salts[0],slot,1000)
            for slot,length in enumerate(lengths)]
(ROOT/'sim/known_input.mem').write_text('\n'.join(
    f'{word:08x}' for job in known_jobs for word in struct.unpack('<26I',test_packet(job)))+'\n')
(ROOT/'sim/known_expected.mem').write_text('\n'.join(
    f'{word:08x}' for password,salt,_,rounds in known_jobs
    for word in hardware_words(digest(password,salt,rounds)))+'\n')
