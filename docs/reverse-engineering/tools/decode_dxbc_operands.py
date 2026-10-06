import struct, json

OPCODES = {int(k): v.replace('OPCODE_','') for k,v in json.load(open('opcode_table.json')).items()}
TYPES = {0:'TEMP',1:'INPUT',2:'OUTPUT',3:'INDEXABLE_TEMP',4:'IMM32',5:'IMM64',6:'SAMPLER',
         7:'RESOURCE',8:'CBUFFER',9:'IMM_CBUFFER',10:'LABEL',27:'UAV'}
INDEXREP = {0:'IMM32',1:'IMM64',2:'REL',3:'IMM32+REL',4:'IMM64+REL'}

def decode_operand(dwords, pos):
    tok = dwords[pos]
    numcomp = tok & 0x3
    seltype = (tok>>2)&0x3  # 0=mask,1=swizzle,2=select1
    otype = (tok>>12)&0xff
    idxdim = (tok>>20)&0x3
    extended = (tok>>31)&1
    p = pos+1
    if extended:
        p += 1  # skip extended token (modifiers) -- not decoding its content
    indices=[]
    for d in range(idxdim):
        rep = (tok >> (22+3*d)) & 0x7
        if rep in (0,3):  # imm32 or imm32+rel
            indices.append(('imm32', dwords[p])); p+=1
        elif rep in (1,4):
            indices.append(('imm64', (dwords[p],dwords[p+1]))); p+=2
        else:
            indices.append(('rel','<reg>'))
    imm=None
    if otype in (4,5):  # immediate value operand: ncomponents dwords follow
        n = 4 if numcomp==2 else (1 if numcomp==1 else 0)
        imm = dwords[p:p+n]; p+=n
    return {'type':TYPES.get(otype,'T%d'%otype),'numcomp':numcomp,'indices':indices,'imm':imm}, p

def disasm_with_operands(shex, max_instr=150000):
    ver, = struct.unpack('<I', shex[0:4])
    total_dwords, = struct.unpack('<I', shex[4:8])
    dwords = struct.unpack('<%dI'%total_dwords, shex[:total_dwords*4])
    pos = 2
    out=[]
    while pos < total_dwords and len(out)<max_instr:
        token = dwords[pos]
        opcode = token & 0x7FF
        length = (token>>24)&0x7F
        mnem = OPCODES.get(opcode,'OP_%d'%opcode)
        if length==0:
            if opcode==0x35:
                length = max(dwords[pos+1],2)
            else:
                length=1
        instr_end = pos+length
        p = pos+1
        ops=[]
        try:
            while p < instr_end:
                o, p = decode_operand(dwords, p)
                ops.append(o)
        except Exception as e:
            ops.append({'error':str(e)})
        out.append((pos,mnem,ops))
        pos = instr_end
    return out

if __name__=='__main__':
    import sys,re
    buf=open(sys.argv[1],'rb').read()
    pos=int(sys.argv[2],16)
    one,total_size,chunk_count = struct.unpack('<III', buf[pos+20:pos+32])
    offs = struct.unpack('<%dI'%chunk_count, buf[pos+32:pos+32+4*chunk_count])
    shex=None
    for co in offs:
        cs=pos+co; fourcc=buf[cs:cs+4]; sz,=struct.unpack('<I',buf[cs+4:cs+8])
        if fourcc==b'SHEX': shex=buf[cs+8:cs+8+sz]
    instrs = disasm_with_operands(shex)
    for i,m,ops in instrs:
        opstr = ' | '.join(
            ('CB[%s][%s]'%(o['indices'][0][1] if o['indices'] else '?', o['indices'][1][1] if len(o['indices'])>1 else '?') if o.get('type')=='CBUFFER'
             else 'imm%s'%(o['imm'],) if o.get('type') in ('IMM32','IMM64')
             else '%s%s'%(o.get('type'), o.get('indices')))
            for o in ops)
        print('%4d %-18s %s'%(i,m,opstr))
