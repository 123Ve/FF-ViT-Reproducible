import ctypes
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
import zlib

ROOT=Path(__file__).resolve().parents[1]

class FirmwareMathTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory(prefix='u3_firmware_test_')
        target=Path(cls.tmp.name)/'test.so'
        source='''#include "accuracy_math.h"
        uint32_t crc(const uint8_t *d, size_t n) {return e07_crc32(d,n);}
        int32_t decode(uint32_t v) {return e07_decode_s19(v);}
        void top(const int32_t *v, unsigned n, uint32_t *t) {e07_top5(v,n,t);}
        int valid(const uint32_t *h) {return e07_valid_header(h,5459,38,0x12345678);}
        '''
        result=subprocess.run(['gcc','-x','c','-','-shared','-fPIC','-std=c11','-Wall','-Wextra','-Werror',
            '-I'+str(ROOT/'firmware'),'-o',str(target)],input=source,text=True,capture_output=True)
        if result.returncode: raise AssertionError(result.stderr)
        cls.lib=ctypes.CDLL(str(target))
        cls.lib.crc.restype=ctypes.c_uint32
        cls.lib.decode.restype=ctypes.c_int32

    @classmethod
    def tearDownClass(cls): cls.tmp.cleanup()

    def test_crc_matches_dataset_writer(self):
        raw=b'123456789'
        self.assertEqual(self.lib.crc(raw,len(raw)),zlib.crc32(raw))

    def test_decode_wraps_and_sign_extends(self):
        for x,y in [(0,0),(0x7ffff,-1),(0x40000,-262144),(0x3ffff,262143),(0xffffffff,-1)]:
            self.assertEqual(self.lib.decode(ctypes.c_uint32(x)),y)

    def test_top5_ignores_padded_classes_with_stable_ties(self):
        v=(ctypes.c_int32*1000)(*([0]*1000)); v[0]=5; v[1]=5; v[2]=9; v[999]=262143
        t=(ctypes.c_uint32*5)();self.lib.top(v,38,t)
        self.assertEqual(list(t),[2,0,1,3,4])

    def test_reject_wrong_count_classes_weights_format(self):
        base=[1,5459,301056,1000,12,38,0x12345678,1000]
        self.assertEqual(self.lib.valid((ctypes.c_uint32*8)(*base)),1)
        for col,value in [(0,2),(1,128),(2,602112),(3,0),(4,11),(5,45),(6,0),(7,38)]:
            h=base.copy();h[col]=value
            self.assertEqual(self.lib.valid((ctypes.c_uint32*8)(*h)),0)

if __name__=='__main__': unittest.main()
