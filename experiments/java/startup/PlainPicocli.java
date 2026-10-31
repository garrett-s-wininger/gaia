import picocli.CommandLine;
import picocli.CommandLine.Option;
import java.util.concurrent.Callable;

@CommandLine.Command(name="plain",mixinStandardHelpOptions=true)
public class PlainPicocli implements Callable<Integer> {
    @Option(names="--token",required=true) String token;
    @Option(names="--count",defaultValue="5") int count;
    public Integer call() {
        if (!token.equals(System.getenv("GAIA_REQUEST_TOKEN"))) throw new IllegalStateException("stale token");
        System.out.println("{\"token\":\""+token+"\",\"sum\":"+((long)count*(count+1)/2)+"}");
        return 0;
    }
    public static void main(String[] args) {
        long start=System.nanoTime();final long[] phases=new long[3];phases[0]=start;
        Runtime.getRuntime().addShutdownHook(new Thread(() -> System.err.println("PHASES {\"main_ns\":"+phases[0]+",\"constructed_ns\":"+phases[1]+",\"executed_ns\":"+phases[2]+",\"hook_ns\":"+System.nanoTime()+"}")));
        CommandLine cli=new CommandLine(new PlainPicocli());phases[1]=System.nanoTime();
        int result=cli.execute(args);phases[2]=System.nanoTime();System.exit(result);
    }
}
