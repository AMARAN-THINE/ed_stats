# @category RE
from ghidra.program.util import DefinedDataIterator
out=getScriptArgs()[0]
targets=['StellarForgeInputSeed','StellarForgeInputBasins','StellarForgeInputMountains','StellarForgeInputVolcanoes','StellarForgeInputMaskVariables','StellarForgeInputCommonVariables','StellarForgeInputEjectaCraters','StellarForgeManager','StellarForgeGalaxy']
fm=currentProgram.getFunctionManager(); rm=currentProgram.getReferenceManager()
rows=[]
for d in DefinedDataIterator.definedStrings(currentProgram):
    try: v=str(d.getValue())
    except UnicodeEncodeError: continue
    if v not in targets: continue
    for r in rm.getReferencesTo(d.getAddress()):
        f=fm.getFunctionContaining(r.getFromAddress())
        if f: rows.append((v,str(f.getEntryPoint()),f.getName(),f.getBody().getNumAddresses()))
rows.sort()
with open(out+'/sf_xrefs.tsv','w') as o:
    for row in rows: o.write('\t'.join(str(x) for x in row)+'\n')
print('SFXREFS DONE',len(rows))
