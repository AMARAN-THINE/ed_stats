# @category RE
# Maps every known REST endpoint path string to its containing (constructor) function.
from ghidra.program.util import DefinedDataIterator
out=getScriptArgs()[0]
targets=set()
with open(out+'/../endpoints.txt') as f:
    for line in f:
        line=line.strip()
        if line: targets.add(line)
fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager()
rows=[]
for d in DefinedDataIterator.definedStrings(currentProgram):
    try:
        v=str(d.getValue())
    except UnicodeEncodeError:
        continue
    if v not in targets:
        continue
    for r in rm.getReferencesTo(d.getAddress()):
        f=fm.getFunctionContaining(r.getFromAddress())
        if f:
            rows.append((v,str(f.getEntryPoint()),f.getName(),f.getBody().getNumAddresses()))
rows.sort()
with open(out+'/endpoint_functions.tsv','w') as o:
    for v,addr,name,size in rows:
        o.write('%s\t%s\t%s\t%d\n'%(v,addr,name,size))
print('ENDPOINTMAP DONE %d'%len(rows))
