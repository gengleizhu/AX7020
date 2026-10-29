"""MD5-crypt $1$ only. Fixed 1000 rounds, 8 units x 12 jobs."""
import hashlib
import struct

def digest(password,salt):
    p=password;s=salt
    alternate=hashlib.md5(p+s+p).digest()
    initial=p+b'$1$'+s+(alternate*((len(p)+15)//16))[:len(p)]
    n=len(p)
    while n:
        initial+=b'\0' if n&1 else p[:1]
        n>>=1
    value=hashlib.md5(initial).digest()
    for i in range(1000):
        data=p if i&1 else value
        if i%3:data+=s
        if i%7:data+=p
        data+=value if i&1 else p
        value=hashlib.md5(data).digest()
    return value

def encode_job(password,salt,job_id):
    if not isinstance(job_id,int) or not 0<=job_id<2**64:
        raise ValueError('Job ID must be uint64')
    if not isinstance(password,bytes) or len(password)>64 or b'\0' in password:
        raise ValueError('Password must be 0..64 bytes, no NUL')
    if not isinstance(salt,bytes) or not 1<=len(salt)<=8 or any(c not in b'./0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz' for c in salt):
        raise ValueError('Salt must be 1..8 crypt-alphabet bytes; original microcode does not support empty salt')
    return struct.pack('<2I',1000,len(salt))+salt.ljust(16,b'\0')+struct.pack('<Q2I',job_id,len(password),0)+password.ljust(64,b'\0')

def encode_batch(jobs,transaction_id):
    if not isinstance(transaction_id,int) or not 0<=transaction_id<2**32:
        raise ValueError('Transaction ID must be uint32')
    if len(jobs)!=96 or len({j[2] for j in jobs})!=96:raise ValueError('96 unique job IDs required')
    return struct.pack('<2I',0x38534d44,transaction_id)+b''.join(encode_job(*j) for j in jobs)

def decode_result(data,transaction_id):
    if len(data)!=2408:raise ValueError('Expected 2408 bytes')
    if struct.unpack_from('<2I',data)!=(0x38524d44,transaction_id):raise ValueError('Header/transaction mismatch')
    result=[];ids=set()
    for u in range(8):
        offset=8+u*300
        unit,magic,cycles=struct.unpack_from('<3I',data,offset)
        if unit!=u or magic!=0x38524d4a:raise ValueError('Unit/header mismatch')
        records=[]
        for j in range(12):
            start=offset+12+j*24
            job_id=struct.unpack_from('<Q',data,start)[0]
            if job_id in ids:raise ValueError('Duplicate result ID')
            ids.add(job_id);records.append((job_id,data[start+8:start+24]))
        result.append({'unit':u,'cycles':cycles,'records':records})
    return result
