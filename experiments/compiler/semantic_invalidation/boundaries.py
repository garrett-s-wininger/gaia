"""Try to falsify AST-only object reuse; every result has a fresh object oracle."""
import argparse
from pathlib import Path
import json
import tempfile
from semantic_cache import Cache,Compiler,sha

CASES={
 'comment':('int f(void){return 7;}\n','int f(void){return 7;}\n/* comment */\n',[]),
 'line-value':('int f(void){return __LINE__;}\n','\nint f(void){return __LINE__;}\n',[]),
 'packing':('#pragma pack(push,1)\nstruct S{char a;long b;};\n#pragma pack(pop)\nint f(void){return sizeof(struct S);}\n','#pragma pack(push,8)\nstruct S{char a;long b;};\n#pragma pack(pop)\nint f(void){return sizeof(struct S);}\n',[]),
 'target-attribute':('__attribute__((target("sse2"))) void f(float*a,float*b){for(int i=0;i<128;i++)a[i]+=b[i];}\n','__attribute__((target("avx"))) void f(float*a,float*b){for(int i=0;i<128;i++)a[i]+=b[i];}\n',[]),
 'inline-assembly':('void f(void){__asm__ volatile("nop");}\n','void f(void){__asm__ volatile("int3");}\n',[]),
 'debug-lines':('int f(void){return 7;}\n','\nint f(void){return 7;}\n',['-g']),
 'macro-stringification':('#define S(x) #x\nconst char*f(void){return S(hello);}\n','#define S(x) #x\nconst char*f(void){return S(world);}\n',[]),
 'cpp-template':('template<int N> int f(){return N;}\nint g(){return f<7>();}\n','template<int N> int f(){return N;}\nint g(){return f<8>();}\n',['-x','c++','-std=c++17'])
}


def run(clang,work,ast_helper=None,direct_ast_helper=None):
    results=[]
    for name,(before,after,extra) in CASES.items():
        directory=work/name;directory.mkdir();source=directory/'probe.c';source.write_text(before)
        command=[str(clang),'--no-default-config','--target=x86_64-unknown-linux-gnu','-O3','-fPIC','-Werror=date-time',*extra,'-c',str(source),'-o',str(directory/'unused.o')]
        compiler=Compiler(command,directory,directory/'compiler',ast_helper,direct_ast_helper);cache=Cache(compiler,'guarded-ast');preparation=cache.seed();entry=cache.entries[0]
        source.write_text(after);oracle=directory/'oracle.o';compiler.full(oracle);expected=sha(oracle.read_bytes())
        for mode in ('text','ast','guarded-ast','ir'):
            selected=Cache(compiler,mode);selected.entries=[entry];output=directory/(mode+'.o');stats=selected.call(output);correct=sha(output.read_bytes())==expected
            results.append(dict(case=name,mode=mode,correct=correct,baseline_object_sha256=sha(entry['object']),oracle_object_sha256=expected,output_object_sha256=sha(output.read_bytes()),object_changed=expected!=sha(entry['object']),**stats))
            if mode!='ast' and not correct:raise ValueError('stronger guard failed '+name)
    return dict(passed=True,checks=len(results),ast_false_hits=[r['case'] for r in results if r['mode']=='ast' and not r['correct']],observations=results)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--clang',type=Path,required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--ast-helper',type=Path);parser.add_argument('--direct-ast-helper',type=Path);args=parser.parse_args()
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='semantic-boundaries-',dir=Path(__file__).parent/'_work') as temp:value=run(args.clang,Path(temp),args.ast_helper,args.direct_ast_helper)
    args.output.write_text(json.dumps(value,indent=2)+'\n');print('Boundary checks',value['checks'],'AST-only false hits',value['ast_false_hits'])
