# @category RE
import json
fm=currentProgram.getFunctionManager()
out=getScriptArgs()[0]
funcs=[(str(f.getEntryPoint()),f.getName(),f.getBody().getNumAddresses()) for f in fm.getFunctions(True)]
with open(out+'/functions.tsv','w') as o:
    for a,n,s in funcs: o.write('%s\t%s\t%d\n'%(a,n,s))
with open(out+'/imports.tsv','w') as o:
    for s in currentProgram.getSymbolTable().getExternalSymbols():
        o.write('%s\t%s\n'%(s.getParentNamespace().getName(),s.getName()))
from ghidra.program.util import DefinedDataIterator
with open(out+'/strings.tsv','w') as o:
    for d in DefinedDataIterator.definedStrings(currentProgram):
        v=d.getValue()
        if v is not None and len(str(v))>=6:
            o.write('%s\t%s\n'%(d.getAddress(),str(v).encode('unicode_escape')))
with open(out+'/blocks.tsv','w') as o:
    for b in currentProgram.getMemory().getBlocks():
        o.write('%s\t%s\t%s\t%d\n'%(b.getName(),b.getStart(),b.getEnd(),b.getSize()))
print('EXPORT DONE %d funcs'%len(funcs))
