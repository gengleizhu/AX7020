"""Offline packet encoder/verifier; does not program hardware."""
import argparse, json
from pathlib import Path
from codec import encode_batch, decode_result, digest

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['encode','verify'])
    parser.add_argument('jobs', type=Path)
    parser.add_argument('packet', type=Path)
    parser.add_argument('--tag', type=lambda value:int(value,0), default=0x12345678)
    args = parser.parse_args()
    rows = json.loads(args.jobs.read_text(encoding='utf-8'))
    jobs = [(bytes.fromhex(row['password_hex']), row['salt'].encode('ascii'),
             row['id'], row.get('rounds',5000)) for row in rows]
    if args.action == 'encode':
        args.packet.write_bytes(encode_batch(jobs,args.tag))
        print('REQUEST_READY units=8 jobs=96 bytes=9992')
        return
    units = decode_result(args.packet.read_bytes(),args.tag)
    for unit in units:
        expected = {job[2]:job for job in jobs[12*unit['unit']:12*(unit['unit']+1)]}
        for job_id, raw in unit['records']:
            password,salt,_,rounds = expected[job_id]
            if raw != digest(password,salt,rounds): raise ValueError('Digest mismatch')
    print('RESPONSE_VERIFIED jobs=96 full_digest_bits=256')

if __name__ == '__main__': main()
