"""Generate independent software-reference RTL vectors. Does not run in DUT."""
import json
import random
import struct
import sys
from pathlib import Path
from passlib.hash import des_crypt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'host'))
from codec import encode_batch, target_parameters, verify_matches

rng = random.Random(20261021)
cases = []
for salt in ['..', 'zz', '55', '/.', './', 'HX', 'ab', 'Z9']:
    words = ['', 'a', '12345678', 'password'] + [
        ''.join(rng.choice('abcXYZ019!') for _ in range(rng.randrange(1, 9))) for _ in range(12)]
    target_word = words[len(cases) % 16]
    target = des_crypt.using(salt=salt).hash(target_word)
    _, low35 = target_parameters(target)
    mask = sum(1 << i for i, word in enumerate(words)
               if target_parameters(des_crypt.using(salt=salt).hash(word))[1] == low35)
    cases.append((words, target, mask))
assert target_parameters(des_crypt.using(salt='55').hash('mypwd123')) == (0x1c7, 0x3cc8731ad)
lines = []
for words, target, mask in cases:
    lines.extend(format(x, '08x') for x in struct.unpack('<36I', encode_batch(words, target)))
    lines.append(format(mask, '08x'))
    assert verify_matches(words, target, mask)
(ROOT / 'sim/vectors.mem').write_text('\n'.join(lines) + '\n')
(ROOT / 'sim/vectors.json').write_text(json.dumps(cases, indent=2))
print('REFERENCE_VECTORS_PASS cases=8 candidates=128 salts=8')
