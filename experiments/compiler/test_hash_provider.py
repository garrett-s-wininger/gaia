"""Digest providers must preserve identities, corruption checks and isolation."""
import os
import unittest

import test_resident_host as previous


@unittest.skipUnless(os.environ.get('GAIA_FAST_HASH')=='1','Set GAIA_FAST_HASH=1 with an accelerated host')
class HashProviderTests(previous.ResidentHistoryTests):
    def request(self,value,extra=(),mode='journal-history',body=None,files=None):
        if mode=='journal-history':mode='journal-history-fast-hash'
        return super().request(value,extra,mode,body,files)

    def test_alternating_providers_preserve_keys_journals_and_objects(self):
        body='#if __has_include("optional.h")\n#include "optional.h"\n#else\n#define VALUE 3\n#endif\nint answer(void){return VALUE;}\n'
        files={str(self.root/f'bytes-{size}'):bytes((i*37)%256 for i in range(size)) for size in (0,1,55,56,63,64,65,1024,65536)}
        first=None
        for mode in ('journal-history-memo','journal-history-fast-hash')*3:
            result=self.consume(self.request(3,mode=mode,body=body,files=files),3)
            if first is None:first=result
            else:
                for field in ('cache_keys','journal_sha256','object_sha256'):self.assertEqual(result[field],first[field])
                self.assertEqual(result['compiler_executions'],0)


if __name__=='__main__':unittest.main()
