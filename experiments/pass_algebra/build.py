"""Build the native experiment with explicit LLVM development paths."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent


def pin(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(a):
    for name in ("odin", "clangxx", "llvm_include", "llvm_library", "output"):
        setattr(a, name, getattr(a, name).resolve())
    a.output.mkdir(parents=True, exist_ok=True)
    obj, library, host = (a.output / n for n in ("liveness.o", "liveness.so", "liveness-host"))
    commands = [
        [str(a.odin), "build", str(HERE / "liveness.odin"), "-file", "-build-mode:obj", "-reloc-mode:pic",
         "-o:speed", "-microarch:native", "-out:" + str(obj)],
        [str(a.clangxx), "-shared", str(obj), "-o", str(library), "-lm"],
        [str(a.clangxx), "-O3", "-std=c++17", "-march=native", "-I" + str(a.llvm_include),
         str(HERE / "host.cpp"), "-L" + str(a.llvm_library), "-Wl,-rpath," + str(a.llvm_library),
         "-lLLVM-22", "-ldl", "-o", str(host)],
    ]
    inputs = [HERE / "build.py", HERE / "liveness.odin", HERE / "host.cpp", a.odin, a.clangxx,
              a.llvm_include / "llvm/Config/llvm-config.h", a.llvm_library / "libLLVM-22.so"]
    before = {str(p): pin(p) for p in inputs}
    start = time.perf_counter_ns()
    for command in commands:
        subprocess.run(command, check=True)
    assert before == {str(p): pin(p) for p in inputs}
    result = {"commands": commands, "ns": time.perf_counter_ns() - start, "inputs_sha256": before,
              "outputs_sha256": {str(p): pin(p) for p in (host, library)},
              "odin_version": subprocess.check_output([a.odin, "version"], text=True),
              "clang_version": subprocess.check_output([a.clangxx, "--version"], text=True),
              "scope": "Native measurement CPU target, not a portable deployment binary; selected SDK identity pins, not a complete header dependency manifest."}
    (a.output / "build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps({"host": str(host), "library": str(library), "build_seconds": result["ns"] / 1e9}))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("odin", "clangxx", "llvm-include", "llvm-library", "output"):
        p.add_argument("--" + n, type=Path, required=True)
    main(p.parse_args())
