"""Offline DMA packet utility. Does not connect to or program hardware."""
import argparse,json
from pathlib import Path
from codec import encode_batch,decode_result,digest

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=['encode','verify'])
    parser.add_argument('jobs',type=Path,help='96 JSON records: id, password_hex, salt')
    parser.add_argument('packet',type=Path,help='request output for encode; response input for verify')
    parser.add_argument('--tag',type=lambda s:int(s,0),default=0x12345678)
    args=parser.parse_args()
    rows=json.loads(args.jobs.read_text(encoding='utf-8'))
    jobs=[(bytes.fromhex(r['password_hex']),r['salt'].encode('ascii'),r['id']) for r in rows]
    request=encode_batch(jobs,args.tag)
    if args.action=='encode':
        args.packet.write_bytes(request)
        print('REQUEST_READY units=8 jobs=96 bytes=9992 tag=%d'%args.tag)
        return
    units=decode_result(args.packet.read_bytes(),args.tag)
    for unit in units:
        expected={i:(p,s) for p,s,i in jobs[12*unit['unit']:12*(unit['unit']+1)]}
        if {i for i,_ in unit['records']}!=set(expected):raise ValueError('Wrong result ID set')
        for i,raw in unit['records']:
            if raw!=digest(*expected[i]):raise ValueError('Digest mismatch for ID %d'%i)
        print('UNIT_VERIFIED unit=%d cycles=%d'%(unit['unit'],unit['cycles']))
    print('RESPONSE_VERIFIED jobs=96 full_digest_bits=128')

if __name__=='__main__':main()
