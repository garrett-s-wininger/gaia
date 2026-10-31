"""Use the pinned package's immutable DGM table with fresh runtime bindings."""
import hashlib,subprocess,zipfile
from pathlib import Path

SOURCE='org/codehaus/groovy/reflection/GeneratedMetaMethod.java'
SCHEMA='GAIA-DGM-BIND-1'
DENSE='''        public static List<DgmMethodRecord> loadDgmInfo() throws IOException {
            ClassLoader loader = DgmMethodRecord.class.getClassLoader();
            try (DataInputStream in = new DataInputStream(new BufferedInputStream(loader.getResourceAsStream("META-INF/dgminfo")))) {
                List<String> names = new ArrayList<>(256);
                for (;;) {
                    String name = in.readUTF(); if (name.isEmpty()) break;
                    int key = in.readInt();
                    if (key < 0 || key >= 100000) throw new IOException("DGM class bound");
                    while (names.size() <= key) names.add(null);
                    names.set(key, name);
                }
                Class[] classes = new Class[names.size()];
                if (classes.length < PRIMITIVE_CLASSES.length) throw new IOException("DGM primitive table");
                System.arraycopy(PRIMITIVE_CLASSES, 0, classes, 0, PRIMITIVE_CLASSES.length);
                for (int i=PRIMITIVE_CLASSES.length; i<names.size(); i++) {
                    String name=names.get(i); if(name == null) continue;
                    try { classes[i] = loader.loadClass(name); }
                    catch (ClassNotFoundException ignored) { /* same unavailable-class policy */ }
                }
                int size=in.readInt();
                if (size < 0 || size > 100000) throw new IOException("DGM record bound");
                List<DgmMethodRecord> result = new ArrayList<>(size);
                for (int i=0;i<size;i++) {
                    DgmMethodRecord record=new DgmMethodRecord();record.className=in.readUTF();record.methodName=in.readUTF();
                    int returnId=in.readInt();
                    if(returnId<0 || returnId>=classes.length) throw new IOException("DGM return ID");
                    record.returnType=classes[returnId];boolean skip=record.returnType==null;
                    int count=in.readInt();if(count<0 || count>4096) throw new IOException("DGM parameter bound");
                    record.parameters=new Class[count];
                    for(int j=0;j<count;j++) {
                        int id=in.readInt();if(id<0 || id>=classes.length) throw new IOException("DGM parameter ID");
                        record.parameters[j]=classes[id];if(classes[id]==null) skip=true;
                    }
                    if(!skip) result.add(record);
                }
                return result;
            }
        }'''

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def checked(cmd):
 p=subprocess.run([str(v) for v in cmd],capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p

def prepare(jdk,jar,sources,work):
 work.mkdir(parents=True,exist_ok=True)
 if sha(sources)!='94a6e1d6ddd94cfe31e64d50a8564026badc72a43f19d380726a787c9a11104b':raise ValueError('pinned Groovy source artifact changed')
 with zipfile.ZipFile(sources) as z:original=z.read(SOURCE).decode()
 if original.count('names.entrySet().parallelStream().forEach')!=1:raise ValueError('pinned DGM source changed')
 variants={'rebuilt':original,'serial':original.replace('names.entrySet().parallelStream().forEach','names.entrySet().stream().forEach')}
 start=original.index('        public static List<DgmMethodRecord> loadDgmInfo() throws IOException {');level=0;end=None
 for i in range(original.index('{',start),len(original)):
  level += (original[i]=='{')-(original[i]=='}')
  if not level:end=i+1;break
 if end is None:raise ValueError('method framing')
 variants['dense']=original[:start]+DENSE+original[end:]
 outputs={};pins={}
 for name,text in variants.items():
  root=work/name;source=root/'source'/SOURCE;source.parent.mkdir(parents=True);source.write_text(text);classes=root/'classes';classes.mkdir()
  checked([jdk/'bin/javac','--release','17','-cp',jar,'-d',classes,source])
  replacements={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class')};target=root/('groovy-'+name+'.jar')
  with zipfile.ZipFile(jar) as inp,zipfile.ZipFile(target,'w') as out:
   for info in inp.infolist():out.writestr(info,replacements.pop(info.filename,inp.read(info)))
   if replacements:raise ValueError('unexpected new public classes: '+str(replacements))
  with zipfile.ZipFile(jar) as inp,zipfile.ZipFile(target) as out:
   for info in inp.infolist():
    if not info.filename.startswith('org/codehaus/groovy/reflection/GeneratedMetaMethod') and inp.read(info)!=out.read(info.filename):raise ValueError('unrelated package change')
  outputs[name]=target;pins[name]=dict(jar_sha256=sha(target),patched_source_sha256=sha(source),dgminfo_sha256=hashlib.sha256(zipfile.ZipFile(target).read('META-INF/dgminfo')).hexdigest())
 return outputs,dict(schema=SCHEMA,base_jar_sha256=sha(jar),source_jar_sha256=sha(sources),variants=pins)
