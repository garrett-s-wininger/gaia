"""A deliberately small schema language, not an OpenAPI/JSON Schema implementation.

Models carry descriptions and fields with scalar or named-record types. Immutable
resolved records feed SQL, Python and Markdown emitters. Recursive references are
legal; consumers do not recursively expand their targets.
"""
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import keyword
import re
import sqlite3


@dataclass(frozen=True)
class Field:
    name: str
    type: str
    description: str


@dataclass(frozen=True)
class Record:
    name: str
    description: str
    fields: tuple[Field, ...]


SCALARS = {'string', 'integer', 'boolean', 'number'}


def identifier(name):
    if not isinstance(name, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*', name) or keyword.iskeyword(name):
        raise ValueError('unsupported identifier: ' + str(name))
    return name


def resolve(payload):
    data = json.loads(payload)
    if data.get('format') != 'gaia-schema-experiment-1':
        raise ValueError('unsupported schema')
    definitions = data['records']
    sqlite_names = set()
    for name in definitions:
        identifier(name)
        # Generated Python decorators and scalar annotations share the module
        # namespace. SQLite identifiers are case-insensitive and reserve sqlite_.
        if name in SCALARS | {'dataclass', 'str', 'int', 'bool', 'float'} or name.lower().startswith('sqlite_'):
            raise ValueError('reserved record name')
        if name.lower() in sqlite_names:
            raise ValueError('case-colliding record name')
        sqlite_names.add(name.lower())
    records = []
    for name, spec in sorted(definitions.items()):
        fields = []
        field_names = set()
        for field, value in sorted(spec['fields'].items()):
            identifier(field)
            if field.lower() in field_names:
                raise ValueError('case-colliding field name')
            field_names.add(field.lower())
            kind = value['type']
            if kind not in SCALARS and kind not in definitions:
                raise ValueError('unresolved type: ' + kind)
            fields.append(Field(field, kind, str(value.get('description', ''))))
        records.append(Record(name, str(spec.get('description', '')), tuple(fields)))
    return tuple(records)


def emit_python(records):
    names = {'string': 'str', 'integer': 'int', 'boolean': 'bool', 'number': 'float'}
    out = ['from __future__ import annotations', 'from dataclasses import dataclass']
    for record in records:
        out.extend(['@dataclass', f'class {record.name}:'])
        out.extend(f'    {field.name}: {names.get(field.type, field.type)}' for field in record.fields)
        if not record.fields:
            out.append('    pass')
    return ('\n'.join(out) + '\n').encode()


def emit_sql(records):
    names = {'string': 'TEXT', 'integer': 'INTEGER', 'boolean': 'INTEGER', 'number': 'REAL'}
    # References are stored as opaque text IDs in this experiment.
    return ('\n'.join('CREATE TABLE "' + record.name + '" (' +
                      ', '.join('"' + field.name + '" ' + names.get(field.type, 'TEXT') for field in record.fields) +
                      ');' for record in records if record.fields) + '\n').encode()


def emit_docs(records):
    out = []
    for record in records:
        out.extend(['## ' + record.name, record.description])
        out.extend(f'- {field.name}: {field.type}: {field.description}' for field in record.fields)
    return ('\n'.join(out) + '\n').encode()


EMITTERS = {'python': emit_python, 'sql': emit_sql, 'docs': emit_docs}


def generate(payload, shared=True, parallel=False):
    records = resolve(payload) if shared else None
    def one(item):
        name, emitter = item
        return name, emitter(records if shared else resolve(payload))
    if parallel:
        with ThreadPoolExecutor(max_workers=3) as executor:
            return dict(executor.map(one, EMITTERS.items()))
    return dict(map(one, EMITTERS.items()))


def consume(name, output):
    if name == 'python':
        # Compile emitted source as a real downstream consumer; no execution of
        # untrusted generated code or dependency on mutable module registration.
        code = compile(output, '<generated-client>', 'exec')
        return len(code.co_code)
    if name == 'sql':
        with sqlite3.connect(':memory:') as connection:
            connection.executescript(output.decode())
            return connection.execute('select count(*) from sqlite_master where type="table"').fetchone()[0]
    return output.count(b'\n## ') + int(output.startswith(b'## '))


def operation(payload, previous=None, cutoff=False):
    outputs = generate(payload)
    consumed = {}
    for name, output in outputs.items():
        # Both controls pay output hashing. Only cutoff may suppress an unchanged
        # downstream operation. This state belongs to one immutable context.
        digest = hashlib.sha256(output).digest()
        if cutoff and previous and previous[name][0] == digest:
            consumed[name] = (digest, previous[name][1], False)
        else:
            consumed[name] = (digest, consume(name, output), True)
    return consumed


def fixture(count=250, fields=12):
    records = {}
    for index in range(count):
        members = {f'field{n:02}': {'type': ('string', 'integer', 'number', 'boolean')[n % 4],
                                  'description': f'Field {n} of record {index}'} for n in range(fields)}
        members['parent'] = {'type': f'Record{(index + 1) % count:05}'}
        records[f'Record{index:05}'] = {'description': f'Record {index}', 'fields': members}
    return json.dumps({'format': 'gaia-schema-experiment-1', 'records': records}).encode()
