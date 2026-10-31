import java.io.*;
import java.nio.charset.StandardCharsets;
import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;

/** Independent whole targets, private compiler/filemanager state per thread. */
public final class TopologyHarness {
    static long cpu() { return ProcessHandle.current().info().totalCpuDuration().orElseThrow().toNanos(); }
    public static void main(String[] args) throws Exception {
        int workers=Integer.parseInt(args[0]);
        if(workers<1 || workers>8)throw new IllegalArgumentException("worker bound");
        Path a=Path.of(args[1]), b=Path.of(args[2]), sdk=Path.of(args[3]), empty=Path.of(args[4]), broken=Path.of(args[5]);
        List<List<Path>> inputs=List.of(CompilerHarness.sourceUnits(a),CompilerHarness.sourceUnits(b));
        List<String> options=List.of("-encoding","UTF-8","-g:none","-proc:none","-implicit:none","-source","25","-target","25","--system",sdk.toString(),"-classpath",empty.toString(),"-sourcepath",a.resolve("empty-sourcepath").toString());
        ThreadLocal<CompilerHarness.Worker> privateWorker=new ThreadLocal<>();
        CountDownLatch ready=new CountDownLatch(workers);
        ThreadPoolExecutor pool=new ThreadPoolExecutor(workers,workers,0,TimeUnit.SECONDS,new ArrayBlockingQueue<>(64),r->new Thread(()->{
            try(CompilerHarness.Worker worker=new CompilerHarness.Worker()) {
                privateWorker.set(worker);ready.countDown();r.run();
            }catch(Exception error){throw new RuntimeException(error);}
        },"topology-compiler"));
        pool.prestartAllCoreThreads();
        if(!ready.await(30,TimeUnit.SECONDS))throw new IllegalStateException("worker startup timeout");
        Map<Integer,Map<String,byte[]>> last=new TreeMap<>();
        System.out.println("READY {\"workers\":"+workers+",\"heap_max\":"+Runtime.getRuntime().maxMemory()+",\"heap_committed\":"+Runtime.getRuntime().totalMemory()+"}");System.out.flush();
        try(BufferedReader reader=new BufferedReader(new InputStreamReader(System.in,StandardCharsets.UTF_8))) {
            for(String line;(line=reader.readLine())!=null;) {
                if(line.equals("stop"))break;
                long begin=System.nanoTime(),cpuBegin=cpu();
                try {
                    if(line.equals("gc")) {
                        System.gc();
                        System.out.println("{\"ok\":true,\"requested_gc\":true,\"wall_ns\":"+(System.nanoTime()-begin)+",\"cpu_ns\":"+(cpu()-cpuBegin)+",\"heap_used\":"+(Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())+",\"heap_committed\":"+Runtime.getRuntime().totalMemory()+"}");System.out.flush();continue;
                    }
                    if(line.equals("check")) {
                        if(last.isEmpty())throw new IllegalStateException("no retained outputs");
                        List<String> values=new ArrayList<>();
                        for(var target:last.entrySet())values.add("\""+target.getKey()+"\":\""+CompilerHarness.consume(target.getValue())+"\"");
                        System.out.println("{\"ok\":true,\"versions\":{"+String.join(",",values)+"}}");System.out.flush();continue;
                    }
                    String[] fields=line.split(" ");
                    if(fields.length!=4 || !fields[0].equals("run") || !fields[1].matches("[A-Za-z0-9_-]{1,80}"))throw new IllegalArgumentException("request framing");
                    int first=Integer.parseInt(fields[2]),count=Integer.parseInt(fields[3]);
                    if(first<0 || count<1 || count>8 || first+count>8)throw new IllegalArgumentException("task bound");
                    last.clear();
                    List<Future<Map<String,byte[]>>> futures=new ArrayList<>();
                    for(int i=0;i<count;i++) {
                        int id=first+i;
                        List<Path> units=fields[1].equals("fail")?List.of(broken):inputs.get(id%2);
                        futures.add(pool.submit(()->privateWorker.get().compile(units,options)));
                    }
                    List<Map<String,byte[]>> compiled=new ArrayList<>();Exception failure=null;
                    for(var future:futures)try{compiled.add(future.get());}catch(Exception error){if(failure==null)failure=error;}
                    if(failure!=null)throw failure;
                    long compiledAt=System.nanoTime();List<String> results=new ArrayList<>();
                    for(int i=0;i<count;i++) {
                        var target=compiled.get(i);int id=first+i;last.put(id,target);
                        results.add("{\"target\":"+id+",\"classes\":"+target.size()+",\"bytes\":"+CompilerHarness.bytes(target)+",\"sha256\":\""+CompilerHarness.digest(target)+"\"}");
                    }
                    System.out.println("{\"ok\":true,\"token\":\""+fields[1]+"\",\"workers\":"+workers+",\"targets\":"+count+",\"units\":"+(count*inputs.get(0).size())+",\"compile_ns\":"+(compiledAt-begin)+",\"wall_ns\":"+(System.nanoTime()-begin)+",\"cpu_ns\":"+(cpu()-cpuBegin)+",\"heap_used\":"+(Runtime.getRuntime().totalMemory()-Runtime.getRuntime().freeMemory())+",\"heap_committed\":"+Runtime.getRuntime().totalMemory()+",\"outputs\":["+String.join(",",results)+"]}");
                } catch(Exception error) {
                    last.clear();System.out.println("{\"ok\":false,\"error\":\""+CompilerHarness.safe(error.toString())+"\"}");
                }
                System.out.flush();
            }
        } finally {
            last.clear();pool.shutdown();if(!pool.awaitTermination(30,TimeUnit.SECONDS))throw new IllegalStateException("worker shutdown timeout");
        }
    }
}
