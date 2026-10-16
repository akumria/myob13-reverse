# Find a string in a Ghidra program, list its references, and decompile the
# referencing functions.
#
# Usage:  analyzeHeadless <projDir> <proj> -import <bin> -postScript find_xref.py <text> [decompile]
# @category MYOB

import sys

from ghidra.app.decompiler import DecompInterface
from ghidra.program.model.symbol import RefType
from ghidra.util.task import ConsoleTaskMonitor


def find_string(prog, needle):
    """Return Data objects whose value contains needle."""
    hits = []
    listing = prog.getListing()
    for data in listing.getDefinedData(True):
        try:
            v = data.getValue()
        except Exception:
            continue
        if v is None:
            continue
        if needle in v:
            hits.append((data.getAddress(), v))
    return hits


def main():
    args = getScriptArgs()
    needle = args[0] if args else None
    do_decompile = len(args) > 1 and args[1] == 'decompile'

    if not needle:
        println('usage: find_xref.py <text> [decompile]')
        return

    prog = currentProgram
    println('== program: %s (%s) ==' % (prog.getName(), prog.getLanguageID()))
    hits = find_string(prog, needle)
    println('== %d string hit(s) for %r ==' % (len(hits), needle))
    for addr, val in hits:
        println('  STRING %s  %s' % (addr, val[:120]))

    if not hits:
        return

    fm = prog.getFunctionManager()
    refmgr = prog.getReferenceManager()
    target_fns = {}
    for addr, _ in hits:
        refs = refmgr.getReferencesTo(addr)
        for ref in refs:
            fa = ref.getFromAddress()
            fn = fm.getFunctionContaining(fa)
            if fn is not None:
                target_fns[fn.getEntryPoint()] = fn
            println('  XREF from %s (%s) type=%s' % (
                fa, fn.getName() if fn else '<no function>', ref.getReferenceType()))

    println('== %d referencing function(s) ==' % len(target_fns))
    for ep, fn in sorted(target_fns.items()):
        println('  FUNC %s  %s  size=%d' % (ep, fn.getName(), fn.getBody().getNumAddresses()))

    if not do_decompile:
        return

    ifc = DecompInterface()
    ifc.openProgram(prog)
    mon = ConsoleTaskMonitor()
    for ep, fn in sorted(target_fns.items()):
        res = ifc.decompileFunction(fn, 120, mon)
        if res.decompileCompleted():
            println('\n---- C: %s @ %s ----' % (fn.getName(), ep))
            println(res.getDecompiledFunction().getC())
        else:
            println('!! decompile failed: %s' % res.getErrorMessage())
    ifc.dispose()


FindXRef().run(find_xref.py)
