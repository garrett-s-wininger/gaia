public class EmptyMain {
    public static void main(String[] args) {
        long start=System.nanoTime();final long[] phases={start,start,start};
        Runtime.getRuntime().addShutdownHook(new Thread(() -> System.err.println("PHASES {\"main_ns\":"+phases[0]+",\"constructed_ns\":"+phases[1]+",\"executed_ns\":"+phases[2]+",\"hook_ns\":"+System.nanoTime()+"}")));
        String token=System.getenv("GAIA_REQUEST_TOKEN");
        if (!args[0].equals(token)) throw new IllegalStateException("stale token");
        System.out.println("{\"token\":\""+token+"\",\"sum\":15}");phases[2]=System.nanoTime();System.exit(0);
    }
}
