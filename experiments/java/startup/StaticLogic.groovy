import groovy.transform.CompileStatic
@CompileStatic
class StaticLogic {
    static long sum(int n) {
        long result = 0
        for (int i=1; i<=n; i++) result += i
        return result
    }
}
