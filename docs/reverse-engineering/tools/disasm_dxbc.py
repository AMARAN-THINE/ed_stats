import struct, re, json, sys

OPCODES = {int(k): v.replace('OPCODE_','') for k,v in json.load(open('opcode_table.json')).items()}

def disasm_shex(shex, max_instr=100000):
    ver, = struct.unpack('<I', shex[0:4])
    total_dwords, = struct.unpack('<I', shex[4:8])
    pos = 8
    end = min(total_dwords*4, len(shex))
    out = []
    while pos+4 <= end and len(out) < max_instr:
        token, = struct.unpack('<I', shex[pos:pos+4])
        opcode = token & 0x7FF
        length = (token >> 24) & 0x7F
        extended = (token >> 31) & 1
        mnem = OPCODES.get(opcode, 'OP_%d'%opcode)
        if length == 0:
            if opcode == 0x35 and pos+8 <= len(shex):  # CUSTOMDATA has explicit length dword
                ext_len, = struct.unpack('<I', shex[pos+4:pos+8])
                length = max(ext_len, 2)
            else:
                length = 1
        raw = shex[pos:pos+length*4]
        out.append((pos, mnem, opcode, length, raw.hex()))
        pos += length*4
    return out, total_dwords

if __name__=='__main__':
    buf = open(sys.argv[1],'rb').read()
    pos = int(sys.argv[2],16)
    one,total_size,chunk_count = struct.unpack('<III', buf[pos+20:pos+32])
    offs = struct.unpack('<%dI'%chunk_count, buf[pos+32:pos+32+4*chunk_count])
    shex=None
    for co in offs:
        cs=pos+co
        fourcc=buf[cs:cs+4]
        sz,=struct.unpack('<I', buf[cs+4:cs+8])
        if fourcc==b'SHEX': shex=buf[cs+8:cs+8+sz]
    instrs, td = disasm_shex(shex)
    for i,(p,m,op,ln,raw) in enumerate(instrs):
        print('%4d  %-20s len=%d  %s'%(i,m,ln,raw[:40]))
