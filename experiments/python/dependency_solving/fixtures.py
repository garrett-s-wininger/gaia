"""Deterministic local wheel graphs. Resolver code never knows their shapes."""
from pathlib import Path
import zipfile


def wheel(root, name, version, dependencies=(), *, requires_python="", extras=(), tag="py3-none-any"):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    normalized = name.replace("-", "_")
    prefix = f"{normalized}-{version}.dist-info/"
    metadata = f"Metadata-Version: 2.3\nName: {name}\nVersion: {version}\n"
    if requires_python:
        metadata += f"Requires-Python: {requires_python}\n"
    metadata += "".join(f"Provides-Extra: {e}\n" for e in extras)
    metadata += "".join(f"Requires-Dist: {d}\n" for d in dependencies)+"\n"
    path = root/f"{normalized}-{version}-{tag}.whl"
    with zipfile.ZipFile(path,"w") as output:
        for member,value in (("METADATA",metadata),("WHEEL",f"Wheel-Version: 1.0\nGenerator: gaia-fixture\nRoot-Is-Purelib: true\nTag: {tag}\n"),("RECORD","")):
            info=zipfile.ZipInfo(prefix+member,(2020,1,1,0,0,0))
            info.external_attr=0o100644 << 16
            output.writestr(info,value)
    return path


def wide(base, widths):
    cases=[]
    for width in widths:
        root=base/f"wide-{width}"
        wheel(root,"wide-root","1.0",[f"wide-leaf-{i:04}>=1,<6" for i in range(width)])
        for i in range(width):
            for version in range(1,6):
                wheel(root,f"wide-leaf-{i:04}",f"{version}.0")
        cases.append({"name":f"wide-{width}","wheelhouse":str(root),"roots":["wide-root==1.0"],"expected_status":"solved"})
    return cases


def generated(base):
    # Preserve the exact original 22-wheel set and expected pip selection.
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parent.parent/"dependency_bundles"))
    from python_native_benchmark import make_wheelhouse
    sys.path.pop(0)
    anchor=base/"anchor"
    expected=make_wheelhouse(anchor)
    cases=[{"name":"original-22", "wheelhouse":str(anchor), "roots":["gaia-app==1.0"], "expected":expected}]
    cases.extend(wide(base,(50,250)))
    root=base/"shared-100"
    wheel(root,"shared-root","1.0",[f"shared-service-{i:03}>=1" for i in range(100)])
    for i in range(100):
        for version in range(1,5):
            wheel(root,f"shared-service-{i:03}",f"{version}.0",[f"shared-common-{i%10:02}>=1,<5"])
    for i in range(10):
        for version in range(1,5):
            wheel(root,f"shared-common-{i:02}",f"{version}.0")
    cases.append({"name":"shared-100","wheelhouse":str(root),"roots":["shared-root==1.0"]})
    root=base/"conflicts"
    wheel(root,"conflict-root","1.0",[f"choice-{i:02}>=1" for i in range(4)]+["z-lock==1.0"])
    for i in range(4):
        for version in range(1,5):
            wheel(root,f"choice-{i:02}",f"{version}.0",[f"shared-core=={version}.0"])
    for version in range(1,5):
        wheel(root,"shared-core",f"{version}.0")
    wheel(root,"z-lock","1.0",["shared-core==1.0"])
    cases.append({"name":"conflicts","wheelhouse":str(root),"roots":["conflict-root==1.0"]})
    root=base/"unsatisfiable"
    wheel(root,"unsat-root","1.0",["unsat-left==1.0","unsat-right==1.0"])
    wheel(root,"unsat-left","1.0",["unsat-common==1.0"])
    wheel(root,"unsat-right","1.0",["unsat-common==2.0"])
    for version in ("1.0","2.0"):
        wheel(root,"unsat-common",version)
    cases.append({"name":"unsatisfiable","wheelhouse":str(root),"roots":["unsat-root==1.0"],"expected_status":"unsatisfiable"})
    for case in cases:
        case.setdefault("expected_status","solved")
    return cases
