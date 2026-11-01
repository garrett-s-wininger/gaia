"""Independent fixed-point oracle and hand-checked LLVM extraction semantics."""
import ctypes as C
import itertools
import json
import os
from pathlib import Path
import random
import subprocess
import unittest

HERE = Path(__file__).resolve().parent
U32P, U64P, U8P = C.POINTER(C.c_uint32), C.POINTER(C.c_uint64), C.POINTER(C.c_uint8)


class Input(C.Structure):
    _fields_ = [(n, C.c_uint32) for n in ("blocks", "values", "words", "reserved")] + [
        (n, U32P) for n in ("succ_offsets", "successors", "pred_offsets", "predecessors")
    ] + [("generate", U64P), ("kill", U64P), ("seed_offsets", U32P), ("seeds", U32P)]


class Scratch(C.Structure):
    _fields_ = [("output", U64P), ("alternate", U64P), ("queue", U32P), ("queued", U8P)]


def oracle(successors, generate, kill):
    live = [set() for _ in successors]
    while True:
        current = [set(g) | (set().union(*(live[s] for s in successors[b])) - set(kill[b]))
                   for b, g in enumerate(generate)]
        if current == live:
            return current
        live = current


def csr(rows):
    offsets, values = [0], []
    for row in rows:
        values.extend(row)
        offsets.append(len(values))
    return (C.c_uint32 * len(offsets))(*offsets), (C.c_uint32 * len(values))(*values)


class LivenessTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        library = os.environ.get("GAIA_LIVENESS_LIBRARY")
        if not library:
            raise unittest.SkipTest("set GAIA_LIVENESS_LIBRARY to the built Odin library")
        cls.library = C.CDLL(library)
        cls.kernel = cls.library.gaia_liveness
        cls.kernel.argtypes = [C.c_uint32, C.POINTER(Input), C.POINTER(Scratch)]
        cls.kernel.restype = C.c_uint64

    def compare(self, successors, generate, kill, values):
        n, words = len(successors), (values + 63) // 64
        pred = [[] for _ in successors]
        seeds = [[] for _ in range(values)]
        gen, kills = (C.c_uint64 * (n * words))(), (C.c_uint64 * (n * words))()
        for b in range(n):
            for s in successors[b]:
                pred[s].append(b)
            for v in generate[b]:
                gen[b * words + v // 64] |= 1 << (v % 64)
                seeds[v].append(b)
            for v in kill[b]:
                kills[b * words + v // 64] |= 1 << (v % 64)
        so, si = csr(successors)
        po, pi = csr(pred)
        vo, vi = csr(seeds)
        data = Input(n, values, words, 0, so, si, po, pi, gen, kills, vo, vi)
        expected = oracle(successors, generate, kill)
        guard = 0x123456789ABCDEF0
        for mode in range(3):
            output = (C.c_uint64 * (n * words + 2))(*([guard] * (n * words + 2)))
            alternate = (C.c_uint64 * (n * words + 2))(*([guard] * (n * words + 2)))
            queue = (C.c_uint32 * (n + 2))(*([0x12345678] * (n + 2)))
            flags = (C.c_uint8 * (n + 2))(*([0x5A] * (n + 2)))
            scratch = Scratch(C.cast(C.byref(output, 8), U64P), C.cast(C.byref(alternate, 8), U64P),
                              C.cast(C.byref(queue, 4), U32P), C.cast(C.byref(flags, 1), U8P))
            work = self.kernel(mode, C.byref(data), C.byref(scratch))
            self.assertNotEqual(work, (1 << 64) - 1)
            actual = [{v for v in range(values) if output[1+b*words+v//64] & (1 << (v % 64))}
                      for b in range(n)]
            self.assertEqual(actual, expected, (mode, successors, generate, kill))
            for buffer, sentinel in ((output, guard), (alternate, guard), (queue, 0x12345678), (flags, 0x5A)):
                self.assertEqual((buffer[0], buffer[-1]), (sentinel, sentinel))
            if values % 64:
                self.assertTrue(all(output[1+b*words+words-1] >> (values % 64) == 0 for b in range(n)))

    def test_exhaustive_two_blocks_two_values(self):
        relations = [[[v for v in range(2) if mask & (1 << (b * 2 + v))] for b in range(2)]
                     for mask in range(16)]
        for successors, generate, kill in itertools.product(relations, repeat=3):
            self.compare(successors, generate, kill, 2)

    def test_random_cycles_and_word_boundaries(self):
        rng = random.Random(731)
        for values in (0, 1, 63, 64, 65, 127, 129):
            for _ in range(25):
                n = rng.randrange(1, 25)
                successors = [rng.sample(range(n), rng.randrange(min(n, 5) + 1)) for _ in range(n)]
                generate = [rng.sample(range(values), rng.randrange(min(values, 8) + 1)) for _ in range(n)]
                kill = [rng.sample(range(values), rng.randrange(min(values, 8) + 1)) for _ in range(n)]
                self.compare(successors, generate, kill, values)

    def test_empty_and_invalid_dispatch(self):
        self.compare([], [], [], 0)
        self.assertEqual(self.kernel(99, None, None), (1 << 64) - 1)

    def test_hand_checked_phi_and_unreachable_extraction(self):
        host = os.environ.get("GAIA_LIVENESS_HOST")
        if not host:
            self.skipTest("set GAIA_LIVENESS_HOST for LLVM extraction tests")
        result = subprocess.run([host, "dump", str(HERE / "fixtures.ll"), os.environ["GAIA_LIVENESS_LIBRARY"]],
                                capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)
        actual = {f["name"]: {name: {f["values"][v] for v in row}
                              for name, row in zip(f["blocks"], f["live_in"])} for f in data["functions"]}
        self.assertEqual(actual, {
            "diamond": {"%entry": {"%condition", "%a", "%b"}, "%left": {"%a"}, "%right": {"%b"}, "%join": set()},
            "loop": {"%entry": {"%n", "%a"}, "%body": {"%n", "%a"}, "%exit": {"%sum"}},
            "unreachable_blocks": {"%entry": {"%a"}, "%dead1": {"%a"}, "%dead2": {"%x"}},
            "self_phi": {"%entry": {"%a"}, "%body": set()},
            "empty_values": {"%entry": set()},
            "invoke_edge": {"%entry": {"%a"}, "%normal": {"%a"}, "%exception": {"%a"}},
        })


if __name__ == "__main__":
    unittest.main()
