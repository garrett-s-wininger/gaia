import java.lang.module.*;
import java.lang.reflect.*;
import java.nio.charset.StandardCharsets;
import java.security.MessageDigest;
import java.util.*;
/** Compare original predicates and indexed membership on actual and synthetic descriptors. */
public class ModuleProbe {
    public static void main(String[] args) throws Exception {
        Class<?> plugin=Class.forName("org.codehaus.groovy.vmplugin.v9.Java9");
        Method index=null;
        try { index=plugin.getDeclaredMethod("unqualifiedPackages",ModuleDescriptor.class,boolean.class);index.setAccessible(true); }
        catch(NoSuchMethodException absent) { }
        List<ModuleDescriptor> modules=new ArrayList<>();
        ModuleFinder.ofSystem().findAll().forEach(r->modules.add(r.descriptor()));
        modules.add(ModuleDescriptor.newModule("synthetic.named").packages(Set.of("a","b","c","d","e"))
            .exports("a").exports("b",Set.of("other.module")).opens("c").opens("d",Set.of("other.module")).build());
        modules.add(ModuleDescriptor.newOpenModule("synthetic.open").packages(Set.of("open.pkg")).build());
        modules.add(ModuleDescriptor.newAutomaticModule("synthetic.automatic").packages(Set.of("auto.pkg")).build());
        int checks=0;
        for(ModuleDescriptor module:modules) for(boolean open:new boolean[]{false,true}) {
            Set<String> membership=index==null?null:(Set<String>)index.invoke(null,module,open);
            Method original=plugin.getDeclaredMethod(open?"isOpen":"isExported",ModuleDescriptor.class,String.class);original.setAccessible(true);
            Set<String> packages=new HashSet<>(module.packages());packages.add("absent.pkg");
            for(String name:packages) {
                boolean expected=(boolean)original.invoke(null,module,name);
                if(membership!=null && expected!=membership.contains(name)) throw new AssertionError(module.name()+":"+name+":"+open);
                checks++;
            }
        }
        List<String> canonical=new ArrayList<>();
        for(String table:new String[]{"CONCEALED_PACKAGES_TO_OPEN","EXPORTED_PACKAGES_TO_OPEN"}) {
            Field field=plugin.getDeclaredField(table);field.setAccessible(true);
            Map<String,Set<String>> map=(Map<String,Set<String>>)field.get(null);
            map.forEach((module,packages)->packages.forEach(name->canonical.add(table+"|"+module+"|"+name)));
        }
        Collections.sort(canonical);
        String digest=HexFormat.of().formatHex(MessageDigest.getInstance("SHA-256").digest(String.join("\n",canonical).getBytes(StandardCharsets.UTF_8)));
        // These touch runtime module identity; no Class/Module/loader objects are serialized.
        Object runtime=plugin.getConstructor().newInstance();Method accessible=plugin.getMethod("checkAccessible",Class.class,Class.class,int.class,boolean.class);
        boolean javaBase=(boolean)accessible.invoke(runtime,ModuleProbe.class,String.class,Modifier.PUBLIC,true);
        boolean unnamed=(boolean)accessible.invoke(runtime,ModuleProbe.class,ModuleProbe.class,Modifier.PUBLIC,true);
        boolean named=(boolean)accessible.invoke(runtime,String.class,ArrayList.class,Modifier.PUBLIC,true);
        if(!javaBase||!unnamed||!named)throw new AssertionError("runtime module access");
        System.out.println("{\"checks\":"+checks+",\"indexed\":"+(index!=null)+",\"table_entries\":"+canonical.size()+",\"digest\":\""+digest+"\"}");
    }
}
