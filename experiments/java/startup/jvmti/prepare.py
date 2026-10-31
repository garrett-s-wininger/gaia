"""Source-rebuilt and package-membership-index variants; fresh VM module discovery."""
import hashlib,subprocess,zipfile
from pathlib import Path
SOURCE='org/codehaus/groovy/vmplugin/v9/Java9.java'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def checked(cmd):
 p=subprocess.run(list(map(str,cmd)),capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr)
 return p
def prepare(jdk,jar,sources,work):
 with zipfile.ZipFile(sources) as z:original=z.read(SOURCE).decode()
 anchor='''            Map<String, ModuleDescriptor> packages = new HashMap<>(1024);
            finder.findAll().stream()
                    .map(ModuleReference::descriptor)
                    .forEach(md -> md.packages().forEach(pn -> packages.putIfAbsent(pn, md)));'''
 replacement='''            Map<String, ModuleDescriptor> packages = new HashMap<>(1024);
            Map<String, Set<String>> exports = new HashMap<>(128);
            Map<String, Set<String>> opens = new HashMap<>(128);
            finder.findAll().stream()
                    .map(ModuleReference::descriptor)
                    .forEach(md -> {
                        md.packages().forEach(pn -> packages.putIfAbsent(pn, md));
                        exports.put(md.name(), unqualifiedPackages(md, false));
                        opens.put(md.name(), unqualifiedPackages(md, true));
                    });'''
 assert original.count(anchor)==1
 optimized=original.replace(anchor,replacement).replace('descriptor == null || isOpen(descriptor, j8pn)','descriptor == null || opens.get(descriptor.name()).contains(j8pn)').replace('isExported(descriptor, j8pn) ? exportedPackagesToOpen','exports.get(descriptor.name()).contains(j8pn) ? exportedPackagesToOpen')
 helper='''    private static Set<String> unqualifiedPackages(final ModuleDescriptor descriptor, final boolean open) {
        Set<String> result = new HashSet<>();
        if (open) {
            for (ModuleDescriptor.Opens entry : descriptor.opens())
                if (!entry.isQualified()) result.add(entry.source());
        } else {
            for (ModuleDescriptor.Exports entry : descriptor.exports())
                if (!entry.isQualified()) result.add(entry.source());
        }
        return result;
    }

'''
 optimized=optimized.replace('    private static boolean isExported(',helper+'    private static boolean isExported(')
 result={}
 for name,text in [('rebuilt',original),('indexed',optimized)]:
  root=work/name;source=root/'source'/SOURCE;source.parent.mkdir(parents=True);source.write_text(text);classes=root/'classes';classes.mkdir()
  p=subprocess.run([str(jdk/'bin/javac'),'--release','17','-cp',str(jar),'-d',str(classes),str(source)],capture_output=True,text=True)
  if p.returncode:raise RuntimeError(p.stderr)
  replacements={p.relative_to(classes).as_posix():p.read_bytes() for p in classes.rglob('*.class')};changed=set(replacements);target=root/('groovy-'+name+'.jar')
  with zipfile.ZipFile(jar) as inp,zipfile.ZipFile(target,'w') as out:
   for info in inp.infolist():out.writestr(info,replacements.pop(info.filename,inp.read(info)))
   if replacements:raise ValueError(replacements)
  with zipfile.ZipFile(jar) as inp,zipfile.ZipFile(target) as out:
   for info in inp.infolist():
    if info.filename not in changed and inp.read(info)!=out.read(info.filename):raise ValueError(info.filename)
  result[name]=dict(jar=str(target),jar_sha256=sha(target),source_sha256=sha(source),changed_entries=sorted(changed))
 return {name:Path(value['jar']) for name,value in result.items()},dict(schema='GAIA-MODULE-PACKAGE-INDEX-1',base_jar_sha256=sha(jar),source_jar_sha256=sha(sources),variants=result)
