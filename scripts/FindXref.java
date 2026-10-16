// Find a string, list references to it, decompile the referencing functions.
// Usage: find_xref <text> [decompile]
//@category MYOB

import java.util.Iterator;

import ghidra.app.decompiler.DecompInterface;
import ghidra.app.decompiler.DecompileResults;
import ghidra.app.script.GhidraScript;
import ghidra.util.task.ConsoleTaskMonitor;

public class FindXref extends GhidraScript {

    @Override
    public void run() throws Exception {
        String[] args = getScriptArgs();
        if (args.length < 1) {
            println("usage: find_xref <text> [decompile]");
            return;
        }
        String needle = args[0];
        boolean decompile = args.length > 1 && args[1].equals("decompile");

        println("== program: " + currentProgram.getName());
        var hits = new java.util.ArrayList<ghidra.program.model.address.Address>();
        var it = currentProgram.getListing().getDefinedData(true);
        while (it.hasNext()) {
            var d = it.next();
            Object v = d.getValue();
            if (v != null && v.toString().contains(needle)) {
                hits.add(d.getAddress());
                println("  STRING " + d.getAddress() + "  " + v.toString());
            }
        }
        println("== " + hits.size() + " hit(s) ==");
        if (hits.isEmpty()) {
            return;
        }

        var fm = currentProgram.getFunctionManager();
        var targets = new java.util.LinkedHashMap<ghidra.program.model.address.Address,
                ghidra.program.model.listing.Function>();
        for (var a : hits) {
            var refs = currentProgram.getReferenceManager().getReferencesTo(a);
            while (refs.hasNext()) {
                var r = refs.next();
                var fn = fm.getFunctionContaining(r.getFromAddress());
                println("  XREF from " + r.getFromAddress() + "  "
                        + (fn == null ? "<none>" : fn.getName())
                        + "  type=" + r.getReferenceType());
                if (fn != null) {
                    targets.put(fn.getEntryPoint(), fn);
                }
            }
        }
        println("== " + targets.size() + " referencing function(s) ==");
        for (var fn : targets.values()) {
            println("  FUNC " + fn.getEntryPoint() + "  " + fn.getName()
                    + "  size=" + fn.getBody().getNumAddresses());
        }

        if (!decompile) {
            return;
        }
        var ifc = new DecompInterface();
        ifc.openProgram(currentProgram);
        var mon = new ConsoleTaskMonitor();
        for (var fn : targets.values()) {
            DecompileResults res = ifc.decompileFunction(fn, 120, mon);
            if (res.decompileCompleted() && res.getDecompiledFunction() != null) {
                println("\n---- C: " + fn.getName() + " @ " + fn.getEntryPoint() + " ----");
                println(res.getDecompiledFunction().getC());
            } else {
                println("!! decompile failed: " + res.getErrorMessage());
            }
        }
        ifc.dispose();
    }
}
