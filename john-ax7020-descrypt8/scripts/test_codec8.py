import sys,struct,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'host'))
from codec8 import encode_superbatch,decode_superresult,verify_superresult

class Tests(unittest.TestCase):
    groups=[['mypwd123']*16 for _ in range(8)]
    targets=['55hMnVAwQjWXI']*8
    def response(self):
        return struct.pack('<2I',0x38524344,42)+b''.join(
            struct.pack('<5I',i,0x31524344,0xffff,562,0xdc000001) for i in range(8))
    def test_encode(self):
        data=encode_superbatch(self.groups,self.targets,42)
        self.assertEqual(len(data),1160)
        self.assertEqual(struct.unpack_from('<2I',data),(0x38534344,42))
    def test_decode_verify(self):
        result=verify_superresult(self.groups,self.targets,decode_superresult(self.response(),42))
        self.assertTrue(all(c['verified_indices']==list(range(16)) for c in result['cores']))
    def test_reject(self):
        with self.assertRaises(ValueError):encode_superbatch(self.groups[:7],self.targets,42)
        with self.assertRaises(ValueError):encode_superbatch(self.groups,self.targets,-1)
        with self.assertRaises(ValueError):decode_superresult(self.response(),43)
        with self.assertRaises(ValueError):decode_superresult(self.response()[:-4],42)
        data=bytearray(self.response());struct.pack_into('<I',data,28,0)
        with self.assertRaises(ValueError):decode_superresult(data,42)
if __name__=='__main__':unittest.main()
