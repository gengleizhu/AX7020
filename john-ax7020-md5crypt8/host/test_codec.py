import struct
import unittest
from codec import digest,encode_job,encode_batch,decode_result

class CodecTests(unittest.TestCase):
    def test_known(self):
        self.assertEqual(digest(b'abc',b'12345678').hex(),'401d63c9a4d1f81504b688da522f0305')
    def test_job(self):
        self.assertEqual(len(encode_job(b'',b'a',2**64-1)),104)
        for p,s in [(b'a',b''),(b'a'*65,b'a'),(b'\0',b'a'),(b'a',b'$'),(b'a',b'a'*9)]:
            with self.assertRaises(ValueError):encode_job(p,s,0)
        for job_id in [-1,2**64,'1']:
            with self.assertRaises(ValueError):encode_job(b'abc',b'a',job_id)
    def test_batch(self):
        jobs=[(b'abc',b'a',i) for i in range(96)]
        self.assertEqual(len(encode_batch(jobs,1)),9992)
        with self.assertRaises(ValueError):encode_batch(jobs[:95],1)
        with self.assertRaises(ValueError):encode_batch([jobs[0]]*96,1)
        for tag in [-1,2**32,'1']:
            with self.assertRaises(ValueError):encode_batch(jobs,tag)
    def test_decode(self):
        packet=struct.pack('<2I',0x38524d44,1)
        for u in range(8):
            packet+=struct.pack('<3I',u,0x38524d4a,12345)
            for j in range(12):packet+=struct.pack('<Q',u*12+j)+digest(b'abc',b'a')
        units=decode_result(packet,1)
        self.assertEqual(len(units),8)
        self.assertEqual(units[7]['records'][-1][0],95)
        with self.assertRaises(ValueError):decode_result(packet,2)
        with self.assertRaises(ValueError):decode_result(packet[:-1],1)
        bad=bytearray(packet);struct.pack_into('<Q',bad,44,0)
        with self.assertRaises(ValueError):decode_result(bad,1)
        for offset in [0,8,12]:
            bad=bytearray(packet);struct.pack_into('<I',bad,offset,0xffffffff)
            with self.assertRaises(ValueError):decode_result(bad,1)

if __name__=='__main__':unittest.main()
