"""Build both adapters and the shared Odin worklist kernel with explicit SDK paths."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(a):
    command = [sys.executable, str(HERE.parent / "build.py")]
    for key, value in vars(a).items():
        command += ["--" + key.replace("_", "-"), str(value.resolve())]
    subprocess.run(command, check=True)
    a.output = a.output.resolve()
    host = a.output / "retained-host"
    base = json.loads((a.output / "build.json").read_text())
    inputs = [HERE / "host.cpp", HERE / "build.py", HERE.parent / "host.cpp", a.clangxx.resolve(),
              a.llvm_include.resolve() / "llvm/Config/llvm-config.h", a.llvm_library.resolve() / "libLLVM-22.so"]
    pins = {str(p): sha(p) for p in inputs}
    command = [str(a.clangxx.resolve()), "-O3", "-std=c++17", "-march=native", "-I" + str(a.llvm_include.resolve()),
               str(HERE / "host.cpp"), "-L" + str(a.llvm_library.resolve()), "-Wl,-rpath," + str(a.llvm_library.resolve()),
               "-lLLVM-22", "-ldl", "-o", str(host)]
    subprocess.run(command, check=True)
    if pins != {str(p): sha(p) for p in inputs}:
        raise RuntimeError("build input changed")
    result = {"kernel_and_original_adapter": base, "command": command, "inputs_sha256": pins,
              "outputs_sha256": {str(host): sha(host), str(a.output / "liveness.so"): sha(a.output / "liveness.so")},
              "scope": "Native CPU target; selected SDK identity pins, not a complete header dependency manifest."}
    (a.output / "retained-build.json").write_text(json.dumps(result, indent=2) + "\n")
    print(host)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("odin", "clangxx", "llvm-include", "llvm-library", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    main(parser.parse_args())
