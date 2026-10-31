import java.nio.file.*;
import java.util.*;
/** Independent JVM consumer; its startup is never counted as native compiler latency. */
public final class NativeOutputCheck {
 public static void main(String[] args)throws Exception {
  Path root=Path.of(args[0]);Map<String,byte[]> classes=new TreeMap<>();
  try(var paths=Files.walk(root)){
   for(Path p:paths.filter(p->p.toString().endsWith(".class")).toList())classes.put(root.relativize(p).toString().replace('/','.').replaceAll("\\.class$",""),Files.readAllBytes(p));
  }
  String version=CompilerHarness.consume(classes);
  if(!version.equals(args[1]))throw new IllegalStateException("version differs: "+version);
  System.out.println("OK "+version+" "+classes.size()+" "+CompilerHarness.digest(classes));
 }
}
