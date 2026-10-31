import groovy.lang.Binding;
import groovy.lang.GroovyShell;
import groovy.lang.GroovySystem;
import groovy.lang.Script;
import org.codehaus.groovy.reflection.GeneratedMetaMethod;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.HexFormat;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

public class FrameworkPhases {
    static String recordDigest(List<GeneratedMetaMethod.DgmMethodRecord> records) throws Exception {
        MessageDigest digest=MessageDigest.getInstance("SHA-256");
        for (var r:records) {
            StringBuilder s=new StringBuilder(r.className).append('|').append(r.methodName).append('|').append(r.returnType.getName());
            for (Class<?> p:r.parameters) s.append('|').append(p.getName());
            digest.update(s.append('\n').toString().getBytes(StandardCharsets.UTF_8));
        }
        return HexFormat.of().formatHex(digest.digest());
    }
    public static void main(String[] args) throws Exception {
        long main=System.nanoTime();String mode=args[0],token=args[1];int seed=Integer.parseInt(args[2]);
        if (!token.equals(System.getenv("GAIA_REQUEST_TOKEN"))) throw new IllegalStateException("stale request token");
        long a=System.nanoTime();
        if (mode.equals("records")) {
            var records=GeneratedMetaMethod.DgmMethodRecord.loadDgmInfo();long b=System.nanoTime();
            System.out.println("{\"mode\":\"records\",\"token\":\""+token+"\",\"records\":"+records.size()+",\"digest\":\""+recordDigest(records)+"\",\"decode_ns\":"+(b-a)+",\"main_ns\":"+main+"}");return;
        }
        String version=GroovySystem.getVersion();var registry=GroovySystem.getMetaClassRegistry();long b=System.nanoTime();
        if (mode.equals("registry")) { System.out.println("{\"mode\":\"registry\",\"token\":\""+token+"\",\"result\":\"ready\",\"groovy\":\""+version+"\",\"registry_ns\":"+(b-a)+",\"main_ns\":"+main+"}"); return; }
        Binding binding=new Binding();binding.setVariable("seed",seed);GroovyShell shell=new GroovyShell(binding);long c=System.nanoTime();
        String source;
        if(mode.equals("metaclass")) source="class LocalBox { int value }; LocalBox.metaClass.bump = { d -> delegate.value + d }; def x=new LocalBox(value:seed); assert x.bump(2)==seed+2; LocalBox.metaClass.bump={d -> delegate.value+d+1}; assert x.bump(2)==seed+3; GroovySystem.metaClassRegistry.removeMetaClass(LocalBox); return seed+3";
        else if(mode.equals("extension")) source="return ('hello'.gaiaSuffix(seed.toString()))";
        else if(mode.equals("loader")) source="def child = new GroovyClassLoader(this.class.classLoader); try { def c=child.parseClass('class FreshBox { static int x=7 }'); return c.x+seed } finally { child.close() }";
        else source="return (1..seed).inject(0L) { x, y -> x + y }";
        Script script=shell.parse(source,"GaiaFrameworkProbe.groovy");long d=System.nanoTime();Object result=script.run();long e=System.nanoTime();
        String resultText=String.valueOf(result);
        if (!resultText.matches("[A-Za-z0-9_-]+")) throw new IllegalStateException("unexpected output");
        System.out.println("{\"mode\":\""+mode+"\",\"token\":\""+token+"\",\"result\":\""+resultText+"\",\"groovy\":\""+version+"\",\"registry_ns\":"+(b-a)+",\"shell_ns\":"+(c-b)+",\"compile_ns\":"+(d-c)+",\"run_ns\":"+(e-d)+",\"main_ns\":"+main+"}");
    }
}
