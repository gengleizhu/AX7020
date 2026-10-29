import json,struct,sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from codec import digest,encode_batch
from passlib.hash import md5_crypt
ALPHABET='./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
def crypt_encode(raw):
    text=''
    for a,b,c in [(0,6,12),(1,7,13),(2,8,14),(3,9,15),(4,10,5)]:
        v=(raw[a]<<16)|(raw[b]<<8)|raw[c]
        for _ in range(4):text+=ALPHABET[v&63];v>>=6
    v=raw[11]
    for _ in range(2):text+=ALPHABET[v&63];v>>=6
    return text
jobs=[]
lengths=[0,1,3,7,8,15,16,31,32,55,56,64]
salts=[b'.',b'a',b'ab',b'12345678',b'./Az09',b'zzzzzzzz',b'55',b'XYZ']
for u in range(8):
    for j,n in enumerate(lengths):
        p=bytes(33+(u*13+j*7+k)%90 for k in range(n));s=salts[u]
        jobs.append((p,s,u*12+j))
        raw=digest(p,s)
        expected=md5_crypt.using(salt=s.decode()).hash(p)
        assert expected=='$1$'+s.decode()+'$'+crypt_encode(raw)
assert digest(b'abc',b'12345678').hex()=='401d63c9a4d1f81504b688da522f0305'
frame=encode_batch(jobs,0x12345678)
(ROOT/'sim/input.mem').write_text('\n'.join(f'{w:08x}' for w in struct.unpack('<2498I',frame))+'\n')
(ROOT/'sim/expected.mem').write_text('\n'.join(f'{w:08x}' for p,s,_ in jobs for w in struct.unpack('<4I',digest(p,s)))+'\n')
(ROOT/'sim/vectors.json').write_text(json.dumps([{'id':i,'password_hex':p.hex(),'salt':s.decode(),'digest':digest(p,s).hex()} for p,s,i in jobs],indent=2))
print('REFERENCE_PASS jobs=96 salt_lengths=1..8 password_lengths=0..64 rounds=1000')
