import java.nio.charset.StandardCharsets;
import java.security.*;
import java.util.*;
import org.codehaus.groovy.vmplugin.VMPluginFactory;
public class ImportProbe {
    public static void main(String[] args)throws Exception{
        var plugin=VMPluginFactory.getPlugin();long begin=System.nanoTime();
        String[][] cases={{"java.lang.","java.util.","java.io.","java.net.","groovy.lang.","groovy.util."},{"java.math.","java.util.concurrent."},{"java.lang."}};
        MessageDigest digest=MessageDigest.getInstance("SHA-256");int count=0;
        for(String[] names:cases){var map=plugin.getDefaultImportClasses(names);for(var e:new TreeMap<>(map).entrySet()){digest.update(e.getKey().getBytes(StandardCharsets.UTF_8));for(var v:new TreeSet<>(e.getValue()))digest.update(v.getBytes(StandardCharsets.UTF_8));count++;}map.clear();}
        System.out.println("{\"digest\":\""+HexFormat.of().formatHex(digest.digest())+"\",\"entries\":"+count+",\"discovery_ns\":"+(System.nanoTime()-begin)+"}");
    }
}
