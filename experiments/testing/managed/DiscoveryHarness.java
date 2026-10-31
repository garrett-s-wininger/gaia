import java.nio.file.*;
import java.util.*;
import java.util.concurrent.*;
import java.util.concurrent.atomic.*;
import java.util.stream.*;
import org.junit.platform.launcher.*;
import org.junit.platform.launcher.core.*;
import org.junit.platform.engine.*;
import static org.junit.platform.engine.discovery.DiscoverySelectors.*;

/** JUnit is already a discovery/execute API; test cross-consumer sharing against it. */
public class DiscoveryHarness {
    static class Results implements TestExecutionListener {
        int successes, failures, dynamic;
        public void dynamicTestRegistered(TestIdentifier id){dynamic++;}
        public void executionFinished(TestIdentifier id,TestExecutionResult result){if(id.isTest()){if(result.getStatus()==TestExecutionResult.Status.SUCCESSFUL)successes++;else failures++;}}
    }
    static List<String> ids(TestPlan p){return p.getRoots().stream().flatMap(r->p.getDescendants(r).stream()).filter(TestIdentifier::isTest).map(TestIdentifier::getUniqueId).sorted().toList();}
    static int consume(TestPlan p){List<String> all=ids(p);Set<String> shards=new HashSet<>();for(int i=0;i<4;i++){final int k=i;for(String id:all)if(Math.floorMod(id.hashCode(),4)==k)if(!shards.add(id))throw new AssertionError("duplicate shard");}if(shards.size()!=all.size())throw new AssertionError("missing shard");return all.hashCode();}
    static TestPlan separate(LauncherDiscoveryRequest request){try(LauncherSession s=LauncherFactory.openSession()){return s.getLauncher().discover(request);}}
    public static void main(String[] args)throws Exception{
        String mode=args[0];int classes=Integer.parseInt(args[1]),epoch=Integer.parseInt(args[2]);
        System.setProperty("fixture.epoch",Integer.toString(epoch));
        LauncherDiscoveryRequest request=LauncherDiscoveryRequestBuilder.request().selectors(selectPackage("gaiafixtures")).filters(EngineFilter.includeEngines("junit-jupiter")).build();
        long begin=System.nanoTime(),discoverBegin=System.nanoTime();
        try(LauncherSession s=LauncherFactory.openSession()){
            Launcher launcher=s.getLauncher();List<TestPlan> plans=new ArrayList<>();
            if(mode.equals("independent-parallel")){
                try(ExecutorService pool=Executors.newFixedThreadPool(3)){
                    List<Future<TestPlan>> fs=new ArrayList<>();for(int i=0;i<3;i++)fs.add(pool.submit(()->separate(request)));for(var f:fs)plans.add(f.get());
                }
            } else if(mode.equals("independent")){for(int i=0;i<3;i++)plans.add(launcher.discover(request));}
            else if(mode.equals("shared")){TestPlan p=launcher.discover(request);for(int i=0;i<3;i++)plans.add(p);}
            else if(!mode.equals("direct"))throw new IllegalArgumentException(mode);
            long discoverNs=System.nanoTime()-discoverBegin;int signature=0;
            if(!plans.isEmpty())for(TestPlan plan:plans){if(!ids(plan).equals(ids(plans.getFirst())))throw new AssertionError("test identity mismatch");int value=consume(plan);if(signature!=0&&signature!=value)throw new AssertionError("consumer mismatch");signature=value;}
            long consumed=System.nanoTime();Results result=new Results();
            if(mode.equals("direct"))launcher.execute(request,result);else launcher.execute(plans.getLast(),result);
            long execution=System.nanoTime()-consumed;
            if(result.failures!=0||result.successes!=classes*(10+epoch)||result.dynamic!=classes*epoch)throw new AssertionError("execution mismatch "+result.successes+" "+result.dynamic);
            System.out.println("{\"mode\":\""+mode+"\",\"epoch\":"+epoch+",\"discovered_static_tests\":"+(plans.isEmpty()?0:ids(plans.getFirst()).size())+",\"dynamic_tests\":"+result.dynamic+",\"executed\":"+result.successes+",\"discovery_ns\":"+discoverNs+",\"consumer_ns\":"+(consumed-discoverBegin-discoverNs)+",\"execution_ns\":"+execution+",\"whole_ns\":"+(System.nanoTime()-begin)+",\"signature\":"+signature+"}");
        }
    }
}
