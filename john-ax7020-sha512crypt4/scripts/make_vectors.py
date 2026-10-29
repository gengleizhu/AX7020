import json, struct, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'host'))
from codec import digest,crypt_string,hardware_words,REQUEST_MAGIC
from passlib.hash import sha512_crypt

lengths=[0,1,2,3,7,8,15,16,24,31,32,47,48,55,56,64]
salts=[b'.',b'./Az09',b'1234567890abcde',b'0123456789abcdef']
def make_jobs(units,rounds):
    return [(bytes(33+(unit*13+slot*7+k)%90 for k in range(length)),
             salts[(unit+slot)%4],unit*16+slot,rounds)
            for unit in range(units) for slot,length in enumerate(lengths)]
jobs=make_jobs(4,10);known=make_jobs(1,1000)
for pw,salt,_,rounds in known:
    assert crypt_string(pw,salt,rounds)==sha512_crypt.using(rounds=rounds).hash(pw,salt=salt.decode())
expected_default=sha512_crypt.using(rounds=5000).hash(b'Hello world!',salt='saltstring')
assert crypt_string(b'Hello world!',b'saltstring',5000).split('$')[-1]==expected_default.split('$')[-1]
def packet(job):
    pw,salt,ident,rounds=job
    return struct.pack('<2I',rounds,len(salt))+salt.ljust(16,b'\0')+struct.pack('<Q2I',ident,len(pw),0)+pw.ljust(64,b'\0')
def write_words(name,words):
    (ROOT/'sim'/name).write_text(''.join(f'{x:08x}\n' for x in words))
frame=struct.pack('<2I',REQUEST_MAGIC,0x12345678)+b''.join(map(packet,jobs))
write_words('input.mem',struct.unpack('<1666I',frame))
write_words('expected.mem',[w for pw,salt,_,rounds in jobs for w in hardware_words(digest(pw,salt,rounds))])
write_words('known_input.mem',[w for j in known for w in struct.unpack('<26I',packet(j))])
write_words('known_expected.mem',[w for pw,salt,_,rounds in known for w in hardware_words(digest(pw,salt,rounds))])
for filename,items in [('vectors.json',jobs),('known_vectors.json',known),('example_jobs.json',make_jobs(4,1000))]:
    (ROOT/'sim'/filename).write_text(json.dumps([dict(id=i,password_hex=p.hex(),salt=s.decode(),rounds=r,digest=digest(p,s,r).hex()) for p,s,i,r in items],indent=2))
report=dict(parallel_jobs=64,parallel_rounds=10,standard_jobs=16,standard_rounds=1000,passlib_crosschecks=16,default_5000_verified=True,default_vector=expected_default)
(ROOT/'reports/reference.json').write_text(json.dumps(report,indent=2))
print('REFERENCE_PASS',report)
