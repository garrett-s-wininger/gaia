import groovy.lang.Binding;
import groovy.lang.GroovyShell;
import groovy.lang.GroovySystem;
import picocli.CommandLine;
import picocli.CommandLine.Option;
import java.util.concurrent.Callable;

@CommandLine.Command(name="framework-probe", mixinStandardHelpOptions=true)
public class Command implements Callable<Integer> {
    @Option(names="--mode", defaultValue="picocli") String mode;
    @Option(names="--count", defaultValue="5") int count;
    @Option(names="--token", required=true) String token;
    public Integer call() {
        if (!token.matches("[A-Za-z0-9_-]+") || count < 0 || count > 10000)
            throw new IllegalArgumentException("request bounds");
        long answer;
        if (mode.equals("picocli")) answer=(long)count*(count+1)/2;
        else if (mode.equals("static")) answer=StaticLogic.sum(count);
        else if (mode.equals("dynamic")) {
            Binding binding=new Binding();binding.setVariable("n",count);
            answer=((Number)new GroovyShell(binding).evaluate("n == 0 ? 0L : (1..n).inject(0L) { a, b -> a + b }", "GaiaExpression.groovy")).longValue();
        } else throw new IllegalArgumentException("unknown mode");
        if (!token.equals(System.getenv("GAIA_REQUEST_TOKEN"))) throw new IllegalStateException("stale request environment");
        String version=mode.equals("picocli") ? "unused" : GroovySystem.getVersion();
        System.out.println("{\"mode\":\""+mode+"\",\"count\":"+count+",\"sum\":"+answer+",\"token\":\""+token+"\",\"groovy\":\""+version+"\"}");
        return 0;
    }
    public static void main(String[] args) { System.exit(new CommandLine(new Command()).execute(args)); }
}
