import java.io.*;
import java.lang.management.*;
import java.nio.file.*;
import java.util.*;
import javax.tools.StandardLocation;

/** The compiler emits ordinary bytecode. An independent JVM consumes the result. */
public final class NativeCompiler {
    static final ThreadMXBean threads = ManagementFactory.getThreadMXBean();
    static long threadCpu() {
        return threads.isCurrentThreadCpuTimeSupported() ? threads.getCurrentThreadCpuTime() : -1;
    }

    public static void main(String[] args) throws Exception {
        Path source = Path.of(args[0]), second = Path.of(args[1]);
        Path sdk = Path.of(args[2]), output = Path.of(args[3]);
        List<Path> firstUnits = CompilerHarness.sourceUnits(source);
        List<Path> secondUnits = CompilerHarness.sourceUnits(second);
        List<String> options = new ArrayList<>(List.of(
            "-encoding", "UTF-8", "-g:none", "-proc:none", "-implicit:none", "-source", "25", "-target", "25",
            "--system", sdk.toString(), "-classpath", output.resolve("empty-classpath").toString(),
            "-sourcepath", output.resolve("empty-sourcepath").toString()));
        if (args.length > 4) {
            int index = options.indexOf("--system");
            options.remove(index); options.remove(index);
        }
        if (threads.isCurrentThreadCpuTimeSupported() && !threads.isThreadCpuTimeEnabled())
            threads.setThreadCpuTimeEnabled(true);
        try (CompilerHarness.Worker worker = new CompilerHarness.Worker();
             BufferedReader reader = new BufferedReader(new InputStreamReader(System.in))) {
            if (args.length > 4) {
                worker.manager.setLocation(StandardLocation.SYSTEM_MODULES, null);
                try (var directories = Files.list(Path.of(args[4]))) {
                    for (Path module : directories.filter(Files::isDirectory).sorted().toList())
                        worker.manager.setLocationForModule(StandardLocation.SYSTEM_MODULES,
                            module.getFileName().toString(), List.of(module));
                }
            }
            System.out.println("READY"); System.out.flush();
            for (String line; (line = reader.readLine()) != null;) {
                if (line.equals("stop")) break;
                if (!Set.of("first", "warm", "edit", "fail").contains(line))
                    throw new IllegalArgumentException("unknown request");
                long begin = System.nanoTime();
                Path current = line.equals("edit") ? second : source;
                List<String> taskOptions = new ArrayList<>(options);
                if (Files.exists(current.resolve("module-info.java")))
                    taskOptions.set(taskOptions.indexOf("-sourcepath") + 1, current.toString());
                List<Path> units = line.equals("fail") ? List.of(output.resolve("broken/Broken.java"))
                    : line.equals("edit") ? secondUnits : firstUnits;
                long compileStart = System.nanoTime(), cpuStart = threadCpu();
                try {
                    Map<String, byte[]> classes = worker.compile(units, taskOptions);
                    long cpuEnd = threadCpu(), compiledAt = System.nanoTime();
                    for (var entry : classes.entrySet()) {
                        Path path = output.resolve(line).resolve(entry.getKey().replace('.', '/') + ".class");
                        Files.createDirectories(path.getParent()); Files.write(path, entry.getValue());
                    }
                    long materializedAt = System.nanoTime();
                    String hash = CompilerHarness.digest(classes);
                    long hashedAt = System.nanoTime();
                    System.out.println("{\"ok\":true,\"classes\":" + classes.size()
                        + ",\"bytes\":" + CompilerHarness.bytes(classes) + ",\"sha256\":\"" + hash
                        + "\",\"compile_ns\":" + (compiledAt - compileStart)
                        + ",\"compile_thread_cpu_ns\":" + (cpuStart < 0 || cpuEnd < 0 ? -1 : cpuEnd - cpuStart)
                        + ",\"materialize_ns\":" + (materializedAt - compiledAt)
                        + ",\"hash_ns\":" + (hashedAt - materializedAt)
                        + ",\"request_ns\":" + (hashedAt - begin) + "}");
                } catch (Throwable error) {
                    System.out.println("{\"ok\":false,\"error\":\"" + CompilerHarness.safe(error.toString())
                        + "\",\"compile_ns\":" + (System.nanoTime() - compileStart) + "}");
                    error.printStackTrace(System.err);
                }
                System.out.flush();
            }
        }
    }
}
