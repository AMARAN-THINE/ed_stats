# @category RE
# Finds strings matching targets, reports referencing functions, decompiles small ones.
from ghidra.program.util import DefinedDataIterator
from ghidra.app.decompiler import DecompInterface
out=getScriptArgs()[0]
targets=['"event":"Fileheader"','2.0/elite/user/login','2.0/edserver/login','2.0/elite/event','2.0/elite/journal','ServerToken (','Display help on the available commands','2.0/server/time','Status.json','Cargo.json','Market.json','NavRoute.json','Backpack.json','ShipLocker.json']
fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager()
ifc=DecompInterface(); ifc.openProgram(currentProgram)
rep=open(out+'/xrefs.txt','w'); dec=open(out+'/decomp.c','w')
seen=set()
for d in DefinedDataIterator.definedStrings(currentProgram):
    v=str(d.getValue())
    t=[x for x in targets if v.startswith(x) or v==x]
    if not t: continue
    for r in rm.getReferencesTo(d.getAddress()):
        f=fm.getFunctionContaining(r.getFromAddress())
        rep.write('%s\t%s\t%s\t%s\n'%(t[0],v[:60].encode('unicode_escape'),r.getFromAddress(),f.getName() if f else None))
        if f and f.getEntryPoint() not in seen and f.getBody().getNumAddresses()<6000:
            seen.add(f.getEntryPoint())
            res=ifc.decompileFunction(f,60,monitor)
            if res.decompileCompleted():
                dec.write('// ==== %s @ %s  (ref "%s")\n%s\n'%(f.getName(),f.getEntryPoint(),t[0],res.getDecompiledFunction().getC()))
rep.close(); dec.close(); print('XREFS DONE')
