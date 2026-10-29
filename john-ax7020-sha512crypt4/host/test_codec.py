import struct,unittest
from codec import *
from passlib.hash import sha512_crypt
class CodecTests(unittest.TestCase):
    def test_reference(self):
        for pw,salt,rounds in [(b'Hello world!',b'saltstring',5000),(b'',b'.',1000),(b'x'*64,b'0123456789abcdef',1001)]:
            self.assertEqual(crypt_checksum(digest(pw,salt,rounds)),sha512_crypt.using(rounds=rounds).hash(pw,salt=salt.decode()).split('$')[-1])
    def test_packet(self):
        jobs=[(b'abc',b's',i,1000) for i in range(64)]
        self.assertEqual(len(encode_batch(jobs,7)),6664)
        for pw,salt,ident,rounds in [(b'x'*65,b's',1,1000),(b'x',b'',1,1000),(b'x',b's',1,999),(b'x',b's',1,1000000000)]:
            with self.assertRaises(ValueError):encode_job(pw,salt,ident,rounds)
        with self.assertRaises(ValueError):encode_batch(jobs[:-1]+[jobs[0]],7)
    def test_decode(self):
        words=[RESPONSE_MAGIC,9]
        for u in range(4):
            words += [u,UNIT_MAGIC,100+u]
            for j in range(16):words += [u*16+j,0]+[u*100+j]*16
        decoded=decode_result(struct.pack('<1166I',*words),9)
        self.assertEqual(decoded[3]['records'][15][0],63)
        self.assertEqual(len(decoded[0]['records'][0][1]),64)
        with self.assertRaises(ValueError):decode_result(struct.pack('<1166I',*words),10)
if __name__=='__main__':unittest.main()
