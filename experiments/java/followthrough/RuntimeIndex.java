import java.io.*;
import java.net.URI;
import java.nio.file.*;
import java.security.*;
import java.util.*;
import org.codehaus.groovy.vmplugin.v9.ClassFinder;
/** Producer only: record exactly the discovery algorithm we are replacing. */
public class RuntimeIndex {
    public static void main(String[] args)throws Exception{
        var map=new TreeMap<>(ClassFinder.find(URI.create("jrt:/modules/java.base/"),"java",true,false));
        try(var out=new DataOutputStream(Files.newOutputStream(Path.of(args[0])))){
            out.writeInt(0x47414931);out.writeUTF(System.getProperty("java.runtime.version"));out.writeInt(map.size());
            for(var e:map.entrySet()){out.writeUTF(e.getKey());var names=new TreeSet<>(e.getValue());out.writeInt(names.size());for(String name:names)out.writeUTF(name);}
        }
        System.out.println("{\"names\":"+map.size()+"}");
    }
}
