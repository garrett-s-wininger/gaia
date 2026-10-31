import ctypes
import math
import os
from pathlib import Path
import unittest
from geometry import bfs_order,morton_order,model_reads


class GeometryModelTests(unittest.TestCase):
    def test_orders_preserve_all_nodes(self):
        edges=[(0,2,5),(2,1,3)]
        self.assertEqual(sorted(bfs_order(5,edges)),list(range(5)))
        self.assertEqual(sorted(morton_order([.1,.2,.3,.5,.5,.5,-1,0,1],3)),[0,1,2])

    def test_cache_model_counts_full_groups(self):
        row=model_reads([0,1,2],[0,1,2,0],[4,4,4],2,8)
        self.assertEqual(row['read_bytes'],20);self.assertEqual(row['group_reads'],3)


@unittest.skipUnless(os.environ.get('GAIA_EMBEDDING_LIBRARY'),'set GAIA_EMBEDDING_LIBRARY for native layout checks')
class NativeGeometryTests(unittest.TestCase):
    def setUp(self):
        self.library=ctypes.CDLL(os.environ['GAIA_EMBEDDING_LIBRARY']);self.call=self.library.gaia_embed
        self.call.argtypes=[ctypes.c_uint32,ctypes.c_uint32,ctypes.c_uint32,ctypes.POINTER(ctypes.c_double),ctypes.POINTER(ctypes.c_double)];self.call.restype=ctypes.c_int32

    def test_zero_iteration_and_invalid_input(self):
        weights=(ctypes.c_double*4)(0,1,1,0);positions=(ctypes.c_double*2)(-1,1)
        self.assertEqual(self.call(2,1,0,weights,positions),0);self.assertEqual(list(positions),[-1,1])
        self.assertEqual(self.call(0,1,1,weights,positions),1)
        weights[0]=-1;self.assertEqual(self.call(2,1,1,weights,positions),2)

    def test_translation_is_removed_with_finite_results(self):
        weights=(ctypes.c_double*9)(0,1,.5,1,0,1,.5,1,0)
        values=[-.2,.1,.3,.4,-.5,.6,.8,.2,-.2]
        first=(ctypes.c_double*9)(*values);second=(ctypes.c_double*9)(*(x+7 for x in values))
        self.assertEqual(self.call(3,3,20,weights,first),0);self.assertEqual(self.call(3,3,20,weights,second),0)
        self.assertTrue(all(math.isfinite(x) for x in first))
        for a,b in zip(first,second):self.assertAlmostEqual(a,b,places=10)


if __name__=='__main__':unittest.main()
