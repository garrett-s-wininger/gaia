"""Caller-owned one-shot digest buffers; library identity is pinned by caller."""
import ctypes


class Blake3:
    def __init__(self,helper):
        self.library=ctypes.CDLL(str(helper))
        self.function=self.library.gaia_blake3
        self.function.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_void_p]
        self.function.restype=None

    def __call__(self,data):
        output=(ctypes.c_ubyte*32)()
        # encode_inputs returns caller-owned bytearray storage. Borrow it rather
        # than copying the whole snapshot merely to satisfy the FFI conversion.
        view=(ctypes.c_ubyte*len(data)).from_buffer(data) if isinstance(data,bytearray) else data
        self.function(view,len(data),output)
        return bytes(output)
