"""Local wheel-metadata sources and a shared resolvelib reference provider.

Only named PEP 508 requirements over an admitted finite wheel set are supported.
No downloads, installed-state preference, sdist/build hooks, or direct URLs.
The pip wheel supplies pinned packaging/resolvelib libraries, not pip's CLI.
"""
from collections import Counter
from dataclasses import dataclass
from email.parser import BytesParser
import hashlib
import json
import os
from pathlib import Path
import sys
import sysconfig
import time
import zipfile

_wheel_override=os.environ.get('GAIA_PIP_WHEEL')
PIP_WHEEL = Path(_wheel_override).expanduser().resolve() if _wheel_override else next(
    (Path(sysconfig.get_path("stdlib"))/"ensurepip/_bundled").glob("pip-*.whl"), None)
if PIP_WHEEL is None or not PIP_WHEEL.is_file():
    raise RuntimeError('Provide a pip wheel with GAIA_PIP_WHEEL, or use Python with ensurepip bundled wheels')
sys.path.insert(0, str(PIP_WHEEL))
from pip._vendor.packaging.markers import default_environment
from pip._vendor.packaging.requirements import Requirement
from pip._vendor.packaging.specifiers import SpecifierSet
from pip._vendor.packaging.tags import sys_tags
from pip._vendor.packaging.utils import canonicalize_name, parse_wheel_filename
from pip._vendor.packaging.version import Version
from pip._vendor.resolvelib import AbstractProvider, BaseReporter, Resolver
from pip._vendor.resolvelib.resolvers import ResolutionImpossible, ResolutionTooDeep
import pip._vendor.packaging as packaging
import pip._vendor.resolvelib as resolvelib
sys.path.pop(0)
from incremental import IncrementalResolver
from trail import TrailResolver


class UnsupportedInput(ValueError):
    pass


def encoded(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def digest(value):
    return hashlib.sha256(encoded(value)).hexdigest()


def parse_requirement(text):
    requirement = Requirement(text)
    if requirement.url:
        raise UnsupportedInput("direct URL/VCS requirements need artifact admission first")
    return requirement


def target_default():
    return {"environment": default_environment(), "tags": [str(t) for t in sys_tags()]}


def read_metadata(path, *, verify_syntax=True):
    with zipfile.ZipFile(path) as wheel:
        names = [n for n in wheel.namelist() if n.count("/") == 1 and n.endswith(".dist-info/METADATA")]
        if len(names) != 1:
            raise ValueError("expected exactly one top-level wheel METADATA")
        raw = wheel.read(names[0])
    message = BytesParser().parsebytes(raw)
    for name in ("Name", "Version"):
        if len(message.get_all(name, [])) != 1:
            raise ValueError(f"invalid metadata {name}")
    dynamic = {s.strip().lower() for s in message.get_all("Dynamic", [])}
    if dynamic & {"requires-dist", "requires-python", "provides-extra"}:
        raise UnsupportedInput("dynamic wheel dependency metadata is unsupported")
    dependencies = message.get_all("Requires-Dist", [])
    requires_python = message.get("Requires-Python", "")
    if verify_syntax:
        for text in dependencies:
            parse_requirement(text)
        SpecifierSet(requires_python)
    metadata = {"name": canonicalize_name(message["Name"]), "version": str(Version(message["Version"])),
                "requires_python": requires_python, "dependencies": dependencies,
                "extras": sorted({canonicalize_name(e) for e in message.get_all("Provides-Extra", [])})}
    return metadata, hashlib.sha256(raw).hexdigest(), len(raw)


def admit(wheelhouse, destination):
    """Certify metadata and content identities once; write portable candidate data.

    Absolute artifact locations are a separate local map, excluded from snapshot
    identity. Consumers pin the inventory/catalog digest supplied by admission.
    """
    start = time.perf_counter()
    records, locations = {}, {}
    if not Path(wheelhouse).is_dir():
        raise NotADirectoryError(wheelhouse)
    files = sorted(Path(wheelhouse).rglob("*.whl"))
    metadata_bytes = artifact_bytes = 0
    for path in files:
        name, version, build, tags = parse_wheel_filename(path.name)
        before = path.stat()
        with path.open("rb") as stream:
            artifact_id = hashlib.file_digest(stream,"sha256").hexdigest()
        metadata, metadata_hash, count = read_metadata(path)
        after = path.stat()
        if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise ValueError("artifact changed during admission")
        if metadata["name"] != name or Version(metadata["version"]) != version:
            raise ValueError("wheel filename and metadata identity differ")
        row = {"id": artifact_id, "filename": path.name, "name": name, "version": str(version),
               "build": list(build), "tags": sorted(str(t) for t in tags),
               "metadata_sha256": metadata_hash, "metadata": metadata}
        if artifact_id in records and records[artifact_id] != row:
            raise ValueError("same artifact bytes with conflicting filename identity")
        records[artifact_id] = row
        locations[artifact_id] = str(path.resolve())
        metadata_bytes += count
        artifact_bytes += before.st_size
    rows = sorted(records.values(), key=lambda r: (r["name"], r["version"], r["id"]))
    snapshot = digest(rows)
    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    paths = {}
    sizes = {}
    for kind in ("inventory", "catalog"):
        selected = rows if kind == "catalog" else [{k: v for k, v in r.items() if k != "metadata"} for r in rows]
        document = {"format": "gaia-local-wheel-"+kind, "version": 1, "snapshot": snapshot,
                    "artifacts": selected, "local_paths": locations}
        body = encoded(document)
        path = destination/(kind+".json")
        path.write_bytes(body)
        paths[kind] = {"path": str(path.resolve()), "sha256": hashlib.sha256(body).hexdigest()}
        sizes[kind] = len(body)
    return {"snapshot": snapshot, "files": len(files), "artifacts": len(rows),
            "projects": len({r["name"] for r in rows}), "artifact_bytes": artifact_bytes,
            "raw_metadata_bytes": metadata_bytes, "index_bytes": sizes, "inputs": paths,
            "admission_seconds": time.perf_counter()-start}


class Source:
    """Boundary: list_candidates(project) and metadata(artifact_id).

    Dependency solving consumes certified metadata only. Actual artifact delivery
    would separately verify the full artifact hash; it is outside this experiment.
    """
    def __init__(self, path, pin, backend):
        if backend not in ("files", "cached", "catalog"):
            raise ValueError("unknown metadata backend")
        body = Path(path).read_bytes()
        if hashlib.sha256(body).hexdigest() != pin:
            raise ValueError("metadata snapshot digest mismatch")
        document = json.loads(body)
        kind = "catalog" if backend == "catalog" else "inventory"
        if document["format"] != "gaia-local-wheel-"+kind or document["version"] != 1:
            raise ValueError("unsupported metadata snapshot")
        self.snapshot, self.backend = document["snapshot"], backend
        self.paths = document["local_paths"]
        self.rows = {r["id"]: r for r in document["artifacts"]}
        if len(self.rows) != len(document["artifacts"]):
            raise ValueError("duplicate artifact identity")
        self.projects = {}
        self.versions = {}
        for row in self.rows.values():
            self.projects.setdefault(row["name"], []).append(row)
            self.versions[row["id"]] = Version(row["version"])
        for rows in self.projects.values():
            # Deterministic policy: latest version, then build tag, then artifact ID.
            rows.sort(key=lambda r: (self.versions[r["id"]], tuple(r["build"]), r["id"]), reverse=True)
        self.cache = {}
        self.counts = Counter(index_bytes=len(body))
        self.metadata_seconds = 0.0

    def list_candidates(self, name):
        self.counts["candidate_queries"] += 1
        return self.projects.get(name, ())

    def metadata(self, artifact_id):
        begin = time.perf_counter()
        try:
            self.counts["metadata_calls"] += 1
            row = self.rows[artifact_id]
            if self.backend == "catalog":
                self.counts["metadata_catalog_hits"] += 1
                return row["metadata"]
            if self.backend == "cached" and artifact_id in self.cache:
                self.counts["metadata_cache_hits"] += 1
                return self.cache[artifact_id]
            self.counts["wheel_opens"] += 1
            metadata, metadata_hash, count = read_metadata(self.paths[artifact_id], verify_syntax=False)
            self.counts["metadata_bytes"] += count
            if (metadata_hash != row["metadata_sha256"] or metadata["name"] != row["name"]
                    or Version(metadata["version"]) != self.versions[artifact_id]):
                raise ValueError("wheel metadata differs from admitted snapshot")
            if self.backend == "cached":
                self.cache[artifact_id] = metadata
            return metadata
        finally:
            self.metadata_seconds += time.perf_counter()-begin


@dataclass(frozen=True)
class Candidate:
    name: str
    artifact_id: str
    extras: frozenset


class Reporter(BaseReporter):
    def __init__(self):
        self.counts = Counter()

    def starting_round(self, index):
        self.counts["rounds"] += 1

    def rejecting_candidate(self, criterion, candidate):
        self.counts["rejections"] += 1

    def resolving_conflicts(self, causes):
        self.counts["conflicts"] += 1

    def pinning(self, candidate):
        self.counts["pins"] += 1


class Session:
    def __init__(self, source, target, *, parsed_cache=True, match_cache=False, heuristic=False, prereleases=False, engine="baseline"):
        if engine not in ("baseline", "incremental", "trail") or (engine != "baseline" and heuristic):
            raise ValueError("incremental engine requires the stable lexical policy")
        self.engine = engine
        self.source, self.target = source, target
        if set(default_environment())-set(target["environment"]) or not all(isinstance(v,str) for v in target["environment"].values()):
            raise ValueError("target requires a complete string-valued marker environment")
        if not target["tags"] or not all(isinstance(t,str) and len(t.split("-"))==3 and all(t.split("-")) for t in target["tags"]):
            raise ValueError("target requires ordered concrete wheel tags")
        self.environment = dict(target["environment"], extra="")
        self.python = Version(self.environment["python_full_version"])
        if self.environment["python_version"] != f"{self.python.major}.{self.python.minor}":
            raise ValueError("target Python marker versions disagree")
        self.tags = {t: i for i, t in enumerate(target["tags"])}
        self.target_id = digest(target)
        self.parsed_cache, self.match_cache = parsed_cache, match_cache
        self.heuristic, self.prereleases = heuristic, prereleases
        self.requirements, self.specifiers, self.matches = {}, {}, {}
        self.satisfaction = {}
        self.counts = Counter()

    def requirement(self, text):
        if self.parsed_cache and text in self.requirements:
            self.counts["requirement_cache_hits"] += 1
            return self.requirements[text]
        self.counts["requirement_parses"] += 1
        value = parse_requirement(text)
        if self.parsed_cache:
            self.requirements[text] = value
        return value

    def python_spec(self, text):
        if self.parsed_cache and text in self.specifiers:
            return self.specifiers[text]
        self.counts["python_spec_parses"] += 1
        value = SpecifierSet(text)
        if self.parsed_cache:
            self.specifiers[text] = value
        return value

    def active(self, requirement, extras=("",)):
        return requirement.marker is None or any(requirement.marker.evaluate(dict(self.environment, extra=e)) for e in extras)

    def dependencies(self, candidate):
        metadata = self.source.metadata(candidate.artifact_id)
        extras = [""] + sorted(candidate.extras.intersection(metadata["extras"]))
        return [r for text in metadata["dependencies"] if self.active(r := self.requirement(text), extras)]

    def solve(self, roots, constraints=(), max_rounds=10000, *, validate=True):
        root_requirements = [r for t in roots if self.active(r := self.requirement(t))]
        constrained = {}
        for text in constraints:
            r = self.requirement(text)
            if r.extras:
                raise UnsupportedInput("constraints cannot request extras")
            if self.active(r):
                constrained.setdefault(canonicalize_name(r.name), []).append(r)
        provider = Provider(self, constrained)
        reporter = Reporter()
        resolver = {"baseline": Resolver, "incremental": IncrementalResolver, "trail": TrailResolver}[self.engine](provider, reporter)
        try:
            result = resolver.resolve(root_requirements, max_rounds=max_rounds)
        except ResolutionImpossible as error:
            return {"status": "unsatisfiable", "selected": [], "causes": sorted({str(c.requirement) for c in error.causes}),
                    "solver": dict(reporter.counts), "provider": dict(provider.counts), "engine_work": getattr(resolver,"work",{})}
        except ResolutionTooDeep:
            return {"status": "round_limit", "selected": [], "solver": dict(reporter.counts), "provider": dict(provider.counts), "engine_work": getattr(resolver,"work",{})}
        # Validate against requirements/metadata independently of provider match cache.
        if validate:
            validate_solution(self, result.mapping, root_requirements, constrained)
        selected = sorted((name, self.source.rows[c.artifact_id]["version"], c.artifact_id, sorted(c.extras))
                          for name, c in result.mapping.items())
        observation = {"status": "solved", "selected": selected, "solver": dict(reporter.counts), "provider": dict(provider.counts), "engine_work": getattr(resolver,"work",{})}
        if not validate:
            observation["_validation"] = (result.mapping, root_requirements, constrained)
        return observation


class Provider(AbstractProvider):
    def __init__(self, session, constraints):
        self.session, self.constraints = session, constraints
        self.counts, self.match_counts = Counter(), {}

    def identify(self, requirement_or_candidate):
        return canonicalize_name(requirement_or_candidate.name)

    def get_preference(self, identifier, resolutions, candidates, information, backtrack_causes):
        return (self.match_counts.get(identifier, 10**12), identifier) if self.session.heuristic else identifier

    def find_matches(self, identifier, requirements, incompatibilities):
        self.counts["find_matches"] += 1
        session = self.session
        reqs = list(requirements[identifier]) + self.constraints.get(identifier, [])
        excluded = set(incompatibilities[identifier])
        if session.match_cache:
            reqs = list({str(r): r for r in reqs}.values())
        extras = frozenset(canonicalize_name(e) for r in reqs for e in r.extras)
        key = (session.source.snapshot, session.target_id, session.prereleases, identifier,
               tuple(sorted(str(r) for r in reqs)), tuple(sorted((c.artifact_id, tuple(sorted(c.extras))) for c in excluded)))
        if session.match_cache and key in session.matches:
            self.counts["match_cache_hits"] += 1
            found = session.matches[key]
        else:
            found = []
            prereleases = session.prereleases or any(r.specifier.prereleases for r in reqs)
            rows = session.source.list_candidates(identifier)
            # Within a version/build preference, prefer the best compatible tag.
            rows = sorted(rows, key=lambda r: (session.source.versions[r["id"]], tuple(r["build"]),
                          -min((session.tags[t] for t in r["tags"] if t in session.tags), default=10**12), r["id"]), reverse=True)
            for row in rows:
                self.counts["candidate_checks"] += 1
                candidate = Candidate(identifier, row["id"], extras)
                version = session.source.versions[row["id"]]
                if candidate in excluded or (version.is_prerelease and not prereleases):
                    continue
                if not any(t in session.tags for t in row["tags"]):
                    continue
                compatible = True
                for requirement in reqs:
                    self.counts["specifier_checks"] += 1
                    if not requirement.specifier.contains(version, prereleases=True):
                        compatible = False
                        break
                if not compatible:
                    continue
                metadata = session.source.metadata(row["id"])
                if not session.python_spec(metadata["requires_python"]).contains(session.python, prereleases=True):
                    continue
                found.append(candidate)
            found = tuple(found)
            if session.match_cache:
                session.matches[key] = found
        self.match_counts[identifier] = len(found)
        return found

    def is_satisfied_by(self, requirement, candidate):
        self.counts["satisfaction_checks"] += 1
        # The value retains the requirement object, so its identity cannot be
        # recycled while this key exists. The session fixes snapshot/target.
        key = (id(requirement), candidate)
        if self.session.match_cache and key in self.session.satisfaction:
            self.counts["satisfaction_cache_hits"] += 1
            return self.session.satisfaction[key][1]
        self.counts["satisfaction_evaluations"] += 1
        row = self.session.source.rows[candidate.artifact_id]
        result = (canonicalize_name(requirement.name) == candidate.name
                and {canonicalize_name(e) for e in requirement.extras}.issubset(candidate.extras)
                and requirement.specifier.contains(self.session.source.versions[row["id"]], prereleases=True))
        if self.session.match_cache:
            self.session.satisfaction[key] = (requirement, result)
        return result

    def get_dependencies(self, candidate):
        self.counts["get_dependencies"] += 1
        return self.session.dependencies(candidate)


def validate_solution(session, mapping, roots, constraints):
    pending = list(roots)
    reachable = set()
    while pending:
        r = pending.pop()
        name = canonicalize_name(r.name)
        if name not in mapping:
            raise ValueError("solution omits required package")
        c = mapping[name]
        row = session.source.rows[c.artifact_id]
        if name != row["name"] or not r.specifier.contains(Version(row["version"]), prereleases=True):
            raise ValueError("solution violates requirement")
        if not {canonicalize_name(e) for e in r.extras}.issubset(c.extras):
            raise ValueError("solution omits requested extras")
        if not all(x.specifier.contains(Version(row["version"]), prereleases=True) for x in constraints.get(name, [])):
            raise ValueError("solution violates constraint")
        if not any(t in session.tags for t in row["tags"]):
            raise ValueError("solution selects incompatible wheel")
        if name in reachable:
            continue
        reachable.add(name)
        # Parse fresh, outside any provider cache. It still reads the same certified source.
        metadata = session.source.metadata(c.artifact_id)
        if not SpecifierSet(metadata["requires_python"]).contains(session.python, prereleases=True):
            raise ValueError("solution violates Requires-Python")
        extras = [""] + sorted(c.extras.intersection(metadata["extras"]))
        for text in metadata["dependencies"]:
            requirement = parse_requirement(text)
            if session.active(requirement, extras):
                pending.append(requirement)
    if reachable != set(mapping):
        raise ValueError("solution contains unreachable packages")
