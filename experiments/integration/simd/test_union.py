import ctypes,os,random,unittest
from pathlib import Path

@unittest.skipUnless(os.environ.get('GAIA_UNION_LIBRARY'),'set GAIA_UNION_LIBRARY')
class UnionTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.lib=ctypes.CDLL(os.environ['GAIA_UNION_LIBRARY']);cls.fn=cls.lib.gaia_union;cls.fn.argtypes=[ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint64),ctypes.c_uint32,ctypes.c_uint64,ctypes.POINTER(ctypes.c_uint32),ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint64)];cls.fn.restype=ctypes.c_int32;cls.features=cls.lib.gaia_init()
 def test_random_tails_zero_duplicate_and_offsets(self):
  rng=random.Random(17)
  for words in [1,2,3,4,5,7,8,9,17,64]:
   rows=11;values=[rng.getrandbits(64) for _ in range(rows*words)];storage=(ctypes.c_uint64*(len(values)+1))(0,*values);matrix=ctypes.cast(ctypes.byref(storage,8),ctypes.POINTER(ctypes.c_uint64))
   for changed in [[],[0],[2,2,10],list(range(rows))]:
    ids=(ctypes.c_uint32*max(1,len(changed)))(*changed);expected=[0]*words
    for i in changed:
     for j in range(words):expected[j]|=values[i*words+j]
    for mode in [0,1]+([2] if self.features&2 else [])+([3] if self.features&4 else []):
     out=(ctypes.c_uint64*(words+2))(*([0xbadc0ffee]*(words+2)));ptr=ctypes.cast(ctypes.byref(out,8),ctypes.POINTER(ctypes.c_uint64));self.assertEqual(self.fn(mode,matrix,rows,words,ids,len(changed),ptr),0);self.assertEqual(list(out)[1:-1],expected);self.assertEqual((out[0],out[-1]),(0xbadc0ffee,0xbadc0ffee))
 def test_bad_dimensions_mode_and_index(self):
  matrix=(ctypes.c_uint64*1)(1);out=(ctypes.c_uint64*1)(99);ids=(ctypes.c_uint32*1)(2)
  for mode,nrows,words,index in [(0,0,1,0),(4,1,1,0),(0,1,0,0),(0,1,1,2)]:
   ids[0]=index;self.assertNotEqual(self.fn(mode,matrix,nrows,words,ids,1,out),0);self.assertEqual(out[0],99)

if __name__=='__main__':unittest.main()
