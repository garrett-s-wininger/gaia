import javax.tools.*;
import java.io.*;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

/** Bounded private compiler contexts; immutable sources/SDK are caller-owned. */
public final class CompilerHarness {
    static final class ClassFile extends SimpleJavaFileObject {
        final ByteArrayOutputStream out=new ByteArrayOutputStream();
        ClassFile(String name,Kind kind){super(URI.create("memory:///"+name.replace('.','/')+kind.extension),kind);}
        public OutputStream openOutputStream(){return out;}
    }
    static final class MemoryManager extends ForwardingJavaFileManager<StandardJavaFileManager> {
        final Map<String,ClassFile> files=new TreeMap<>();
        MemoryManager(StandardJavaFileManager manager){super(manager);}
        public JavaFileObject getJavaFileForOutput(Location location,String name,JavaFileObject.Kind kind,FileObject sibling){
            ClassFile file=new ClassFile(name,kind);if(files.put(name,file)!=null)throw new IllegalStateException("duplicate class output");return file;
        }
        Map<String,byte[]> bytes(){Map<String,byte[]> result=new TreeMap<>();files.forEach((name,file)->result.put(name,file.out.toByteArray()));return result;}
    }
    static final class Worker implements AutoCloseable {
        final JavaCompiler compiler;final StandardJavaFileManager manager;
        Worker(){compiler=ToolProvider.getSystemJavaCompiler();if(compiler==null)throw new IllegalStateException("jdk.compiler unavailable");manager=compiler.getStandardFileManager(null,Locale.ROOT,StandardCharsets.UTF_8);}
        Map<String,byte[]> compile(List<Path> sources,List<String> options) throws Exception {
            DiagnosticCollector<JavaFileObject> diagnostics=new DiagnosticCollector<>();MemoryManager memory=new MemoryManager(manager);
            boolean okay=compiler.getTask(null,memory,diagnostics,options,null,manager.getJavaFileObjectsFromPaths(sources)).call();manager.flush();
            if(!okay){StringBuilder text=new StringBuilder();for(var d:diagnostics.getDiagnostics())text.append(d.getKind()).append(':').append(d.getCode()).append(':').append(d.getLineNumber()).append(';');throw new IllegalArgumentException(text.toString());}
            return memory.bytes();
        }
        public void close() throws IOException {manager.close();}
    }
    static final class BytesLoader extends ClassLoader {
        final Map<String,byte[]> classes;
        BytesLoader(Map<String,byte[]> classes){super(ClassLoader.getPlatformClassLoader());this.classes=classes;}
        protected Class<?> findClass(String name)throws ClassNotFoundException {byte[] bytes=classes.get(name);if(bytes==null)throw new ClassNotFoundException(name);return defineClass(name,bytes,0,bytes.length);}
    }
    static String digest(Map<String,byte[]> files)throws Exception {
        MessageDigest all=MessageDigest.getInstance("SHA-256");for(var e:files.entrySet()){all.update(e.getKey().getBytes(StandardCharsets.UTF_8));all.update((byte)0);all.update(MessageDigest.getInstance("SHA-256").digest(e.getValue()));}return HexFormat.of().formatHex(all.digest());
    }
    static long bytes(Map<String,byte[]> files){long n=0;for(var value:files.values())n+=value.length;return n;}
    static long rss(){try{for(String line:Files.readAllLines(Path.of("/proc/self/status")))if(line.startsWith("VmRSS:"))return Long.parseLong(line.trim().split("\\s+")[1])*1024;}catch(Exception ignored){}return 0;}
    static String safe(String s){return s.replace("\\","\\\\").replace("\"","\\\"").replace("\n","\\n").replace("\r","\\r");}
    static String consume(Map<String,byte[]> classes)throws Exception {
        BytesLoader loader=new BytesLoader(classes);
        Class<?> specClass=loader.loadClass("picocli.CommandLine$Model$CommandSpec");Object spec=specClass.getMethod("create").invoke(null);
        Class<?> optionClass=loader.loadClass("picocli.CommandLine$Model$OptionSpec");Object builder=optionClass.getMethod("builder",String[].class).invoke(null,(Object)new String[]{"--count"});
        builder.getClass().getMethod("type",Class.class).invoke(builder,Integer.class);Object option=builder.getClass().getMethod("build").invoke(builder);specClass.getMethod("addOption",optionClass).invoke(spec,option);
        Class<?> cliClass=loader.loadClass("picocli.CommandLine");Object cli=cliClass.getConstructor(Object.class).newInstance(spec);Object parsed=cliClass.getMethod("parseArgs",String[].class).invoke(cli,(Object)new String[]{"--count","7"});
        Object value=parsed.getClass().getMethod("matchedOptionValue",String.class,Object.class).invoke(parsed,"--count",-1);if(!Integer.valueOf(7).equals(value))throw new IllegalStateException("in-memory consumer differs");return String.valueOf(cliClass.getField("VERSION").get(null));
    }
    static List<Path> sourceUnits(Path source)throws IOException {
        List<Path> units;try(var stream=Files.walk(source)){units=stream.filter(p->p.toString().endsWith(".java")).sorted(Comparator.comparingLong((Path p)->{try{return -Files.size(p);}catch(IOException e){throw new UncheckedIOException(e);}})).toList();}
        if(units.isEmpty()||units.size()>64)throw new IllegalArgumentException("source unit bound");return units;
    }
    public static void main(String[] args)throws Exception {
        String strategy=args[0];int count=Integer.parseInt(args[1]);Path source=Path.of(args[2]),jar=Path.of(args[3]),sdk=Path.of(args[4]),output=Path.of(args[5]);boolean materialize=Boolean.parseBoolean(args[6]);
        if(count<1||count>4)throw new IllegalArgumentException("worker bound");
        List<Path> units=sourceUnits(source);List<Path> secondUnits=sourceUnits(args.length>7?Path.of(args[7]):source);
        List<String> options=List.of("-encoding","UTF-8","-g:none","-proc:none","-implicit:none","-source","25","-target","25","--system",sdk.toString(),"-classpath",jar.toString(),"-sourcepath",source.resolve("empty-sourcepath").toString());
        Worker sequential=null;ThreadPoolExecutor executor=null;ThreadLocal<Worker> privateWorker=new ThreadLocal<>();
        if(strategy.equals("batch"))sequential=new Worker();
        else if(strategy.equals("pool")){
            CountDownLatch ready=new CountDownLatch(count);
            executor=new ThreadPoolExecutor(count,count,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(64),r->new Thread(()->{try(Worker worker=new Worker()){privateWorker.set(worker);ready.countDown();r.run();}catch(Exception e){throw new RuntimeException(e);}},"gaia-javac-worker"));
            executor.prestartAllCoreThreads();if(!ready.await(30,TimeUnit.SECONDS))throw new IllegalStateException("worker initialization timeout");
        }else throw new IllegalArgumentException("unknown strategy");
        Map<String,byte[]> last=null;long requests=0;
        System.out.println("READY {\"workers\":"+(executor==null?1:count)+",\"rss_bytes\":"+rss()+"}");System.out.flush();
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))){
            for(String line;(line=reader.readLine())!=null;){
                if(line.equals("stop"))break;
                if(line.equals("check")){
                    if(last==null)throw new IllegalStateException("no compiled bytes");long b=System.nanoTime();List<String> versions=new ArrayList<>();
                    if(last.keySet().iterator().next().startsWith("target0.")) {
                        for(int i=0;i<2;i++){String prefix="target"+i+".";Map<String,byte[]> target=new TreeMap<>();for(var e:last.entrySet())if(e.getKey().startsWith(prefix))target.put(e.getKey().substring(prefix.length()),e.getValue());versions.add(consume(target));}
                    } else versions.add(consume(last));
                    System.out.println("{\"ok\":true,\"versions\":[\""+String.join("\",\"",versions)+"\"],\"consumer_ns\":"+(System.nanoTime()-b)+"}");System.out.flush();continue;
                }
                if(line.length()>128||!line.matches("[A-Za-z0-9_-]+"))throw new IllegalArgumentException("request token bound");
                boolean pair=line.startsWith("pair-");
                List<List<Path>> targetUnits=line.equals("fail")?List.of(List.of(output.getParent().resolve("broken/Broken.java"))):pair?List.of(units,secondUnits):List.of(units);
                long start=System.nanoTime();Map<String,byte[]> compiled=new TreeMap<>();
                try{
                    List<Map<String,byte[]>> targets=new ArrayList<>();
                    if(executor==null){for(var target:targetUnits)targets.add(sequential.compile(target,options));}
                    else{
                        List<Future<Map<String,byte[]>>> futures=new ArrayList<>();for(var target:targetUnits)futures.add(executor.submit(()->privateWorker.get().compile(target,options)));
                        Exception failure=null;for(var future:futures){try {targets.add(future.get());}catch(Exception error){if(failure==null)failure=error;}}if(failure!=null)throw failure;
                    }
                    for(int i=0;i<targets.size();i++)for(var e:targets.get(i).entrySet()){String name=(pair?"target"+i+".":"")+e.getKey();if(compiled.put(name,e.getValue())!=null)throw new IllegalStateException("duplicate class output");}
                    long compiledAt=System.nanoTime();if(materialize)for(var e:compiled.entrySet()){Path target=output.resolve(line).resolve(e.getKey().replace('.','/')+".class");Files.createDirectories(target.getParent());Files.write(target,e.getValue());}
                    long materializedAt=System.nanoTime();String hash=digest(compiled);long hashedAt=System.nanoTime();last=compiled;requests++;
                    System.out.println("{\"ok\":true,\"token\":\""+line+"\",\"requests\":"+requests+",\"units\":"+targetUnits.stream().mapToInt(List::size).sum()+",\"targets\":"+targetUnits.size()+",\"classes\":"+compiled.size()+",\"bytes\":"+bytes(compiled)+",\"sha256\":\""+hash+"\",\"compile_ns\":"+(compiledAt-start)+",\"materialize_ns\":"+(materializedAt-compiledAt)+",\"hash_ns\":"+(hashedAt-materializedAt)+",\"rss_bytes\":"+rss()+",\"heap_used_bytes\":"+(Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())+"}");
                }catch(Exception error){last=null;System.out.println("{\"ok\":false,\"token\":\""+line+"\",\"error\":\""+safe(error.toString())+"\"}");}
                System.out.flush();
            }
        }finally{
            last=null;if(sequential!=null)sequential.close();if(executor!=null){executor.shutdown();if(!executor.awaitTermination(30,TimeUnit.SECONDS))throw new IllegalStateException("worker shutdown timeout");}
        }
    }
}
