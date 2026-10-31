/** Isolated Java9 initialization closure; no agent, no preinitialized Groovy state. */
public class InitProbe {
    public static void main(String[] args) throws Exception {
        String token=args[0];
        if(!token.equals(System.getenv("GAIA_REQUEST_TOKEN")))throw new IllegalArgumentException("stale token");
        long begin=System.nanoTime();
        Class.forName("org.codehaus.groovy.vmplugin.v9.Java9",true,InitProbe.class.getClassLoader());
        long elapsed=System.nanoTime()-begin;
        System.out.println("{\"token\":\""+token+"\",\"init_ns\":"+elapsed+"}");
    }
}
