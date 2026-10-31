"""Experimental AST candidate matching; exact pre-optimization IR is the guard.

Clang's diagnostic AST dump is NOT assumed to be a complete code-generation
identity. Equal normalized ASTs only justify checking the stronger compiler IR.
"""
import hashlib
import json
from pathlib import Path
import re
import resource
import subprocess
import time

ID_KEYS={'id','previousDecl','parentDeclContextId','typeAliasDeclId','referencedMemberDecl','canonicalDecl'}
LIMIT=128*1048576


def sha(body):return hashlib.sha256(body).hexdigest()


def canonical_ast(body):
    if len(body)>LIMIT:raise ValueError('AST bound')
    tree=json.loads(body);ids={};nodes=0
    def walk(value):
        nonlocal nodes
        if isinstance(value,dict):
            nodes+=1
            for key in list(value):
                if key in ('loc','range'):del value[key];continue
                item=value[key]
                if key in ID_KEYS and isinstance(item,str) and re.fullmatch('0x[0-9a-fA-F]+',item):
                    if item=='0x0':value[key]='null-id'
                    else:value[key]=ids.setdefault(item,'node-'+str(len(ids)))
                else:walk(item)
        elif isinstance(value,list):
            for item in value:walk(item)
    walk(tree);encoded=json.dumps(tree,sort_keys=True,separators=(',',':')).encode()
    return encoded,dict(ast_raw_bytes=len(body),ast_canonical_bytes=len(encoded),ast_nodes=nodes,ast_ids=len(ids))


def without_output(command):
    result=[];i=0
    while i<len(command):
        if command[i]=='-o':i+=2;continue
        if command[i]!='-c':result.append(command[i])
        i+=1
    return result


def run(command,cwd,output):
    begin=time.perf_counter();cpu=resource.getrusage(resource.RUSAGE_CHILDREN)
    with output.open('wb') as stream:process=subprocess.run(command,cwd=cwd,stdout=stream,stderr=subprocess.PIPE,timeout=180)
    after=resource.getrusage(resource.RUSAGE_CHILDREN)
    if process.returncode:raise RuntimeError(process.stderr.decode(errors='replace'))
    if output.stat().st_size>LIMIT:raise ValueError('compiler output bound')
    return dict(seconds=time.perf_counter()-begin,cpu_seconds=(after.ru_utime+after.ru_stime)-(cpu.ru_utime+cpu.ru_stime),stderr=process.stderr.decode())


class Compiler:
    def __init__(self,command,cwd,work,ast_helper=None,direct_ast_helper=None):
        self.ast_helper=ast_helper;self.direct_ast_helper=direct_ast_helper;self.command=list(command);self.cwd=Path(cwd);self.work=Path(work);self.work.mkdir(parents=True,exist_ok=True);self.base=without_output(command)
        sources=[x for x in command if x.endswith(('.c','.cc','.cpp'))]
        if len(sources)!=1:raise ValueError('single source command required')
        self.source=Path(sources[0]);self.counter=0
    def full(self,output):
        command=self.command.copy();command[command.index('-o')+1]=str(output)
        # Object stdout is unused; retain independent diagnostics.
        return run(command,self.cwd,self.work/'object-stdout')
    def ast(self):
        if self.direct_ast_helper:
            path=self.work/'direct-ast.json';args=[v for v in self.base if v!=str(self.source)]
            stats=run([str(self.direct_ast_helper),str(self.cwd),str(self.source),*args],self.cwd,path)
            counts=json.loads(path.read_text());encoded=counts.pop('sha256').encode();stats.update(counts,canonical_seconds=0.0);return encoded,stats
        path=self.work/'ast.json';stats=run([*self.base,'-fsyntax-only','-Xclang','-ast-dump=json'],self.cwd,path)
        begin=time.perf_counter()
        if self.ast_helper:
            process=subprocess.run([str(self.ast_helper),str(path)],check=True,capture_output=True,text=True,timeout=60);counts=json.loads(process.stdout);encoded=counts.pop('sha256').encode();counts['native_fingerprint']=True
        else:encoded,counts=canonical_ast(path.read_bytes())
        stats.update(counts,canonical_seconds=time.perf_counter()-begin)
        return encoded,stats
    def preprocess(self):
        path=self.work/'preprocessed.i';stats=run([*self.base,'-E'],self.cwd,path)
        body=path.read_bytes();stats['preprocessed_bytes']=len(body);return body,stats

    def ir(self):
        path=self.work/'module.ll';stats=run([*self.base,'-S','-emit-llvm','-Xclang','-disable-llvm-passes','-o',str(path)],self.cwd,self.work/'ir-stdout')
        body=path.read_bytes()
        if len(body)>LIMIT:raise ValueError('IR bound')
        # Keep source filename, all attributes, module flags, debug metadata and
        # inline assembly. Even comments are retained; no semantic elision.
        stats['ir_bytes']=len(body);return body,stats


class Cache:
    def __init__(self,compiler,mode):
        if mode not in ('text','ast','guarded-ast','ir'):raise ValueError('cache mode')
        self.compiler=compiler;self.mode=mode;self.entries=[]
    def seed(self):
        source=self.compiler.source.read_bytes();output=self.compiler.work/'seed.o';full=self.compiler.full(output)
        ast,ast_stats=self.compiler.ast();ir,ir_stats=self.compiler.ir()
        self.entries=[dict(source=sha(source),ast=ast,ir=ir,object=output.read_bytes())]
        return dict(full=full,ast=ast_stats,ir=ir_stats)
    def call(self,output):
        begin=time.perf_counter();source=self.compiler.source.read_bytes();key=sha(source);result=dict(text_hash_bytes=len(source),ast=None,ir=None,full=None,hit=False,ast_equal=False,ir_equal=None)
        for entry in self.entries:
            if entry['source']==key:
                output.write_bytes(entry['object']);result.update(hit=True,reason='text');result['seconds']=time.perf_counter()-begin;return result
        ast=None;ir=None
        if self.mode=='ir':
            ir,result['ir']=self.compiler.ir()
            for entry in self.entries:
                if entry['ir']==ir:
                    output.write_bytes(entry['object']);result.update(hit=True,reason='ir',ir_equal=True);result['seconds']=time.perf_counter()-begin;return result
        elif self.mode!='text':
            ast,result['ast']=self.compiler.ast()
            for entry in self.entries:
                if entry['ast']!=ast:continue
                result['ast_equal']=True
                if self.mode=='guarded-ast':
                    if ir is None:ir,result['ir']=self.compiler.ir()
                    result['ir_equal']=entry['ir']==ir
                    if not result['ir_equal']:continue
                output.write_bytes(entry['object']);result.update(hit=True,reason=self.mode);result['seconds']=time.perf_counter()-begin;return result
        result['full']=self.compiler.full(output)
        # No hidden warm-cache insertion: measured edits always start from the
        # baseline seed. This is a bounded one-candidate feasibility experiment.
        result.update(reason='compiled',seconds=time.perf_counter()-begin);return result
