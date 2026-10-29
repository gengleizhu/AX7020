import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from codec import encode_batch, decode_result, target_parameters, verify_matches

class CodecTests(unittest.TestCase):
    target='55hMnVAwQjWXI'
    def test_upstream_vector(self):
        self.assertEqual(target_parameters(self.target),(0x1c7,0x3cc8731ad))
    def test_frame(self):
        raw=encode_batch(['mypwd123']*16,self.target)
        self.assertEqual(len(raw),144)
        self.assertEqual(raw[16:24],b'mypwd123')
    def test_bad_candidates(self):
        for words in [[],['123456789']*16,['a\0b']*16,['中文']*16]:
            with self.assertRaises((ValueError,UnicodeError)):encode_batch(words,self.target)
    def test_bad_hash(self):
        for target in ['$2b$bad','abc','55hMnVAwQjWXJ','55hMnVAwQjW?!']:
            with self.assertRaises(ValueError):target_parameters(target)
    def test_response(self):
        self.assertEqual(decode_result(struct.pack('<4I',0x31524344,5,502,0xdc000001))['provisional_mask'],5)
        with self.assertRaises(ValueError):decode_result(struct.pack('<4I',0x31524344,5,502,0xdc000005))
        with self.assertRaises(ValueError):decode_result(struct.pack('<4I',0x31524344,5,502,0xdc000100))
    def test_full_recheck(self):
        self.assertEqual(verify_matches(['mypwd123','wrong'],self.target,3),[0])

if __name__=='__main__':unittest.main()
