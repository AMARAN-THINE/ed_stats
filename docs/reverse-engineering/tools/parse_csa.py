import struct, re, json

def parse_dxbc_chunks(buf, start):
    assert buf[start:start+4]==b'DXBC'
    one, total_size, chunk_count = struct.unpack('<III', buf[start+20:start+32])
    chunk_offsets = struct.unpack('<%dI'%chunk_count, buf[start+32:start+32+4*chunk_count])
    chunks = {}
    for co in chunk_offsets:
        cstart = start + co
        fourcc = buf[cstart:cstart+4]
        csize, = struct.unpack('<I', buf[cstart+4:cstart+8])
        cdata = buf[cstart+8:cstart+8+csize]
        chunks.setdefault(fourcc, []).append(cdata)
    return total_size, chunks

def cstr(buf, off):
    end = buf.index(b'\x00', off)
    return buf[off:end].decode('ascii', 'replace')

def parse_rdef(data):
    const_buf_count, const_buf_offset, bound_resource_count, bound_resource_offset, tmaj,tmin,flags,creator_offset = struct.unpack('<8I', data[0:32])
    cbuffers=[]
    for i in range(const_buf_count):
        base = const_buf_offset + i*24
        name_off, var_count, var_offset, size, flags2, ctype = struct.unpack('<IIIIII', data[base:base+24])
        name = cstr(data, name_off)
        vars_=[]
        for v in range(var_count):
            vbase = var_offset + v*40
            vname_off, voffset, vsize = struct.unpack('<III', data[vbase:vbase+12])
            vname = cstr(data, vname_off)
            vars_.append((vname,voffset,vsize))
        cbuffers.append((name,size,vars_))
    resources=[]
    for i in range(bound_resource_count):
        base = bound_resource_offset + i*32
        name_off, rtype, retT, dim, numsamples, bindpt, bindcount, rflags = struct.unpack('<8I', data[base:base+32])
        resources.append((cstr(data,name_off), bindpt, bindcount))
    return cbuffers, resources

def parse_signature(data):
    count, unk = struct.unpack('<II', data[0:8])
    entries=[]
    for i in range(count):
        base = 8 + i*24
        name_off, semidx, systype, comptype, reg, mask = struct.unpack('<IIIIII', data[base:base+24])
        entries.append((cstr(data,name_off), semidx, reg))
    return entries

def find_entry_name(buf, search_start, limit=400):
    region = buf[search_start:search_start+limit]
    for m in re.finditer(rb'[ -~]{6,}', region):
        s = m.group().decode('ascii')
        if re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', s) and len(s) > 8:
            return s
    return None

results=[]
for fname in ['Scatter.csa','TerrainComputeShadersDP.csa','TerrainComputeShadersNvidia.csa','TerrainComputeShaders.csa']:
    buf = open('csa/'+fname,'rb').read()
    dxbc_positions = [m.start() for m in re.finditer(b'DXBC', buf)]
    file_entries=[]
    for pos in dxbc_positions:
        try:
            total_size, chunks = parse_dxbc_chunks(buf, pos)
        except Exception:
            continue
        ep = find_entry_name(buf, pos+total_size, 300)
        cbuf_info=[]
        resources=[]
        if b'RDEF' in chunks:
            try:
                cbuffers, resources = parse_rdef(chunks[b'RDEF'][0])
                cbuf_info = [{'name':n,'size':s,'vars':[{'n':vn} for vn,vo,vs in vs_]} for n,s,vs_ in cbuffers]
                resources = [{'name':r[0],'bind':r[1]} for r in resources]
            except Exception as e:
                cbuf_info=[{'error':str(e)}]
        isgn=osgn=None
        if b'ISGN' in chunks:
            try: isgn=[e[0] for e in parse_signature(chunks[b'ISGN'][0])]
            except Exception as e: isgn=['err']
        if b'OSGN' in chunks:
            try: osgn=[e[0] for e in parse_signature(chunks[b'OSGN'][0])]
            except Exception as e: osgn=['err']
        file_entries.append({'pos':hex(pos),'entry_point':ep,'size':total_size,'cbuffers':cbuf_info,'resources':resources,'isgn':isgn,'osgn':osgn})
    results.append({'file':fname,'count':len(file_entries),'shaders':file_entries})
    print(fname, 'parsed', len(file_entries))
    for e in file_entries[:3]:
        print('  ', e['entry_point'], 'cbuffers=', [c.get('name') for c in e['cbuffers']])

json.dump(results, open('dxbc_parsed2.json','w'), indent=1)
print('DONE')
