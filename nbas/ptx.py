#!/usr/bin/env python3
# coding: utf-8

# todo: n:1 直接生成64位add mul指令

from .grammar import *


def ptx_new_reg(kernel):
    r_idx = kernel.reg_count + 256
    r_str = f'%r{r_idx}'
    kernel.reg_set.add(r_idx)
    kernel.reg_count += 1
    return r_str


def ptx_new_reg64(kernel):
    rd_idx = kernel.reg64_count
    kernel.reg64_count += 1
    return f'%dr{rd_idx}'


def ptx_ord(r):
    r_str = r.lower()
    if '1' == r_str:
        return '', 1
    elif '0' == r_str:
        return '', 0

    if m := re.search(rf'%?(?P<type>[ud]?[rxp])(?P<ord>\d+)', r_str):
        return f"%{m.group('type')}", int(m.group('ord'), base=10)
    else:
        raise Exception(f'Cannot recognize reg {r}')


def ptx_pack(kernel, instr, r1, r2):
    rd_idx = kernel.reg64_count
    instr.add_ptx('mov', f'.b64 %dr{rd_idx}, {{{r1}, {r2}}};')
    kernel.reg64_count += 1
    return f'%dr{rd_idx}'


def ptx_unpack(instr, r1, r2, rd1):
    instr.add_ptx('mov', f'.b64 {{{r1}, {r2}}}, {rd1};')


def ptx_r2d(kernel, instr, r_str):
    r_t, r_o = ptx_ord(r_str)
    if r_t:
        return ptx_pack(kernel, instr, f'{r_t}{r_o}', f'{r_t}{r_o + 1}')
    elif r_o == 1:
        raise Exception(f'pred reg {r_str} not support')
    else:
        return f'{r_o}'


def ptx_i(captured_dict, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    i_str = captured_dict[name]
    if f'{name}neg' in captured_dict and captured_dict[f'{name}neg']:
        i_str = f'-{i_str}'
    return i_str


def ptx_p(captured_dict, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    p_str = f"%{captured_dict[name].lower()}"
    if 'pt' in p_str:
        p_str = '1'
    if f'{name}not' in captured_dict and captured_dict[f'{name}not']:
        if p_str != '1':
            p_str = f'!{p_str}'
        else:
            p_str = '0'
    return p_str


def ptx_r(kernel, captured_dict, instr, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    r_str = f"%{captured_dict[name].lower()}"
    if 'rz' in r_str:
        r_str = '0'
    else:
        type_str = captured_dict['type'] if 'type' in captured_dict and captured_dict['type'] else ''
        if '64' in type_str and 'rd' not in name:
            r_str = ptx_r2d(kernel, instr, r_str)
            new_reg = ptx_new_reg64
            t_str = '64'
        else:
            new_reg = ptx_new_reg
            t_str = '32'
        if f'{name}abs' in captured_dict and captured_dict[f'{name}abs']:
            d = new_reg(kernel)
            instr.add_ptx('abs', f'.s{t_str} {d}, {r_str};')
            r_str = d

        if f'{name}neg' in captured_dict and captured_dict[f'{name}neg']:
            d = new_reg(kernel)
            instr.add_ptx('neg', f'.s{t_str} {d}, {r_str};')
            r_str = d
    return r_str


def ptx_cname(kernel, captured_dict, instr):
    if captured_dict['cname'] is None and captured_dict['adim'] is None:
        return ''

    name_str = captured_dict['cname']
    offset = captured_dict['adim'] if captured_dict['adim'] else 0

    const0_map = {
        'BLOCK_DIM_X': '%ntid.x',
        'BLOCK_DIM_Y': '%ntid.y',
        'BLOCK_DIM_Z': '%ntid.z',
        'GRID_DIM_X': '%nctaid.x',
        'GRID_DIM_Y': '%nctaid.y',
        'GRID_DIM_Z': '%nctaid.z',
    }
    const0_dict = kernel.CONST0_VAL_61.copy() if kernel.arch < 70 else kernel.CONST0_VAL_75.copy()

    type_str = captured_dict['type'] if 'type' in captured_dict and captured_dict['type'] else ''
    if '64' in type_str:
        t_str = '64'
        new_reg = ptx_new_reg64
    else:
        t_str = '32'
        new_reg = ptx_new_reg

    if name_str in const0_dict:
        if name_str == 'STACK' and kernel.frame_size:
            r_str = f'__local_depot+{kernel.frame_size}'
        elif name_str not in const0_map:
            r_str = f'[{name_str}]'
        else:
            r_str = new_reg(kernel)
            instr.add_ptx('mov', f'.u{t_str} {r_str}, {const0_map[name_str]};')
    elif 'mov' in instr.op.lower() or 'ld' in instr.op.lower():
        r_str = f'[{name_str}+{offset}]'
    else:
        r_str = new_reg(kernel)
        ss_str = 'param' if 'ARG_' in name_str else 'const'
        instr.add_ptx('ld', f'.{ss_str}.b{t_str} {r_str}, [{name_str}+{offset}];')
    if f'cabs' in captured_dict and captured_dict[f'cabs']:
        d = new_reg(kernel)
        instr.add_ptx('abs', f'.s{t_str} {d}, {r_str};')
        r_str = d
    if f'cneg' in captured_dict and captured_dict[f'cneg']:
        d = new_reg(kernel)
        instr.add_ptx('neg', f'.s{t_str} {d}, {r_str};')
        r_str = d
    return r_str


def ptx_ir(kernel, captured_dict, instr, i_name, r_name):
    c = ''
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(kernel, captured_dict, instr, r_name)
    return c


def ptx_irc(kernel, captured_dict, instr, i_name, r_name):
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(kernel, captured_dict, instr, r_name)
    else:
        c = ptx_cname(kernel, captured_dict, instr)
    return c


def ptx_rc(kernel, captured_dict, instr, r_name):
    if r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(kernel, captured_dict, instr, r_name)
    else:
        c = ptx_cname(kernel, captured_dict, instr)
    return c


def ptx_addr(kernel, captured_dict, instr):
    if 'cname' in captured_dict and captured_dict['cname']:
        return ptx_cname(kernel, captured_dict, instr)
    ss = instr.op[-1]
    cd = captured_dict.copy()
    if ss in ['L', 'S', 'C']:
        cd['type'] = '32'
    else:
        cd['type'] = '64'
    a = ptx_r(kernel, cd, instr, 'rad')
    if 'rax' in cd and cd['rax']:
        x = cd['rax'][2:]
        if cd['type'] == '32':
            ax = ptx_new_reg(kernel)
            instr.add_ptx('mul', f'.lo.u32 {ax}, {a}, {x};')
        else:
            ax = ptx_new_reg64(kernel)
            instr.add_ptx('mul', f'.lo.u64 {ax}, {a}, {x};')
        a = ax
    b = ptx_r(kernel, cd, instr, 'rad2')
    if a in ['0', '-0', '|0|', '']:
        if ss == 'S':
            a = '%s+'
        else:
            a = ''
    else:
        a = f'{a}+'
    c = ptx_i(captured_dict, 'adim')
    c = int(c, base=0) if c else 0
    if b:
        b += f'+{c}'
    else:
        b = c
    return f'[{a}{b}]'


ptx_ignore_instrs = ['NOP', 'MEMBAR', 'SSY', 'PBK', 'BMOV', 'BSSY', 'BSYNC']

ppred = fr'U?P[0-7T]'
preg = fr'U?R[Z0-9]+'

pp = fr'(?P<pp>{ppred})'
pq = fr'(?P<pq>{ppred})'
pc = fr'(?P<pcnot>\!)?(?P<pc>{ppred})'
pcc1 = fr'(?P<pcc1>{ppred})'
pcc2 = fr'(?P<pcc2>{ppred})'
px1 = fr'(?P<px1not>\!)?(?P<px1>{ppred})'
px2 = fr'(?P<px2not>\!)?(?P<px2>{ppred})'
ra = fr'(?P<raneg>[\-~])?(?P<raabs>\|)?(?P<ra>{preg})\|?'
rb = fr'(?P<rbneg>[\-~])?(?P<rbabs>\|)?(?P<rb>{preg})\|?'
rc = fr'(?P<rcneg>[\-~])?(?P<rcabs>\|)?(?P<rc>{preg})\|?'
rd = fr'(?P<rd>{preg})'
pim = fr'(?P<pim>(?P<neg>\-)?{immed})'
pim2 = fr'(?P<pim2>(?P<neg>\-)?{immed})'
puim = fr'(?P<puim>{immed})'
imlut = fr'(?P<imlut>{immed})'
imask = fr'(?P<imask>{immed})'
adim = fr'(?P<adim>(?P<adneg>\-)?{immed})'
paddr = fr'\[(?:(?P<rad>{preg})(?P<rax>\.X(4|8|16))?(?P<ratype>\.64|\.U32)?)?' \
        rf'(?:\s*\+?\s*(?P<rad2>{preg}))?(?:\s*\+?\s*{adim})?\]'

caddr = rf'(?P<cneg>\-)?(?P<cabs>\|)?c(\[0x3\]\s*)?' \
        rf'\[((?P<rad>{preg})|(?P<cname>[a-zA-Z_]\w*))?(?:\s*\+?\s*{adim})?\]\|?'


def ptx_mov(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_irc(kernel, captured_dict, instr, 'pim', 'ra')
    if a:
        instr.add_ptx('mov', f'.b32 {d}, {a};')
    else:
        type_str = captured_dict['type']
        if '32@' in type_str:
            global_name = captured_dict['gname']
            dr = ptx_new_reg64(kernel)
            instr.add_ptx('mov', f'.u64 {dr}, {global_name};')
            d_t, d_idx = ptx_ord(d)
            if '32@lo' in type_str:
                ptx_unpack(instr, f'{d_t}{d_idx}', f'{d_t}{d_idx + 1}', dr)
            else:
                ptx_unpack(instr, f'{d_t}{d_idx - 1}', f'{d_t}{d_idx}', dr)
        else:
            instr.ptx = None


def ptx_ldst(kernel, captured_dict, instr):
    op = instr.op
    if op in ['LDL', 'STL']:
        ss = '.local'
    elif op in ['LDS', 'STS']:
        ss = '.shared'
    elif 'LDC' in op:
        ss = '.param' if 'cname' in captured_dict and captured_dict['cname'] and 'ARG_' in captured_dict[
            'cname'] else '.const'
    else:
        ss = '.global'

    cache_str = ''
    sync_str = ''
    nc = ''
    if 'const' in captured_dict and captured_dict['const']:
        const_str = f'{captured_dict["const"]}'
        if const_str == '.CONSTANT':
            nc = '.nc'
        elif const_str == '.STRONG':
            sync_str = '.volatile'

    cd = captured_dict.copy()
    cd['type'] = ''
    if 'LD' in op:
        d = ptx_r(kernel, cd, instr, 'rd')
        d_t, d_idx = ptx_ord(d)
    else:
        d = ptx_r(kernel, cd, instr, 'rc')
        d_t, d_idx = ptx_ord(d)

    if captured_dict['type'] and '64' in captured_dict['type']:
        if d_idx == -1:
            d = f'{{0, 0}}'
        else:
            d = f'{{{d_t}{d_idx}, {d_t}{d_idx + 1}}}'
    elif captured_dict['type'] and '128' in captured_dict['type']:
        if d_idx == -1:
            d = f'{{0, 0, 0, 0}}'
        else:
            d = f'{{{d_t}{d_idx}, {d_t}{d_idx + 1}, {d_t}{d_idx + 2}, {d_t}{d_idx + 3}}}'

    adr = ptx_addr(kernel, captured_dict, instr)

    if 'LD' in op:
        op = 'ld'
        dabc = f'{d}, {adr}'
    else:
        op = 'st'
        dabc = f'{adr}, {d}'

    type_str = '.u32'
    v_str = ''
    if captured_dict['type']:
        if '64' in captured_dict['type']:
            v_str = '.v2'
        elif '128' in captured_dict['type']:
            v_str = '.v4'
        elif '32' not in captured_dict['type']:
            type_str = captured_dict['type'].lower()
    instr.add_ptx(op, f'{sync_str}{ss}{cache_str}{nc}{v_str}{type_str} {dabc};')


def ptx_isetp(kernel, captured_dict, instr):
    cmp_str = captured_dict['cmp'].lower()
    bool_str = captured_dict['bool'].lower()
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    p = ptx_p(captured_dict, 'pp')
    q = ptx_p(captured_dict, 'pq')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_p(captured_dict, 'pc')

    ex = captured_dict['EX'].lower() if captured_dict['EX'] else ''
    xx = ptx_p(captured_dict, 'px1')

    m = None
    if ex:
        for i in reversed(kernel.instrs[:instr.line_num]):
            op = i.op
            rest = re.sub(r'\.reuse', '', i.rest)
            if m := re.search(grammar_ptx['ISETP'][0]['rule'], op + rest):
                cd = m.groupdict()
                pp = ptx_p(cd, 'pp')
                pcmp_str = cd['cmp'].lower()
                pbool_str = cd['bool'].lower()
                ptype_str = '.u32' if cd['U32'] else '.s32'
                if pp == xx:
                    # s64的前一个指令可能是u32
                    if (pcmp_str != cmp_str) or (pbool_str != bool_str) or (ptype_str[2:] != type_str[2:]):
                        instr.ptx = None
                        return None
                    pa = ptx_r(kernel, cd, instr, 'ra')
                    pb = ptx_irc(kernel, cd, instr, 'pim', 'rb')
                    a = ptx_pack(kernel, instr, pa, a)
                    b = ptx_pack(kernel, instr, pb, b)
                    type_str = type_str.replace('32', '64')
                    break
        if not m:
            instr.ptx = None
            return None

    if 'p' not in q:
        q = ''
    else:
        q = f'|{q}'
    if not c or (c == '1' and '.and' == bool_str) or (c == '0' and '.or' == bool_str):
        rest = f'{cmp_str}{type_str} {p}{q}, {a}, {b};'
    else:
        rest = f'{cmp_str}{bool_str}{type_str} {p}{q}, {a}, {b}, {c};'
    instr.add_ptx('setp', rest)


def ptx_exit(kernel, captured_dict, instr):  # perfect
    instr.add_ptx('ret', ';')


def ptx_bra(kernel, captured_dict, instr):
    uni = '.uni' if captured_dict['U'] else ''
    instr.add_ptx('bra', f'{uni} {captured_dict["label"]};')


def ptx_s2r(kernel, captured_dict, instr):
    type_str = '.b32'
    r_str = ptx_r(kernel, captured_dict, instr, 'rd')
    r_t, r_idx = ptx_ord(r_str)
    if instr.op == 'CS2R' and not captured_dict['type']:
        type_str = '.b64'
        r_str = ptx_new_reg64(kernel)
    sr_str = captured_dict['sr']
    if 'SRZ' == sr_str:
        sr_str = '0'
    else:
        sr_str = f"%{sr_str[3:].lower()}"
    instr.add_ptx('mov', f'{type_str} {r_str}, {sr_str};')
    if '64' in type_str:
        ptx_unpack(instr, f'{r_t}{r_idx}', f'{r_t}{r_idx + 1}', r_str)


def ptx_lop3(kernel, captured_dict, instr):
    pand = captured_dict['PAND'].lower() if captured_dict['PAND'] else ''
    p = ptx_p(captured_dict, 'pp')
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_r(kernel, captured_dict, instr, 'rc')
    lut = ptx_i(captured_dict, 'imlut')
    x = ptx_p(captured_dict, 'pc')

    if d == '0':
        d = ptx_new_reg(kernel)
    instr.add_ptx('lop3', f'.b32 {d}, {a}, {b}, {c}, {lut};')
    if p:
        instr.add_ptx('setp', f'.ne.b32 {p}, {d}, 0;')


def ptx_shf(kernel, captured_dict, instr):
    lr = captured_dict['lr'].lower()
    mode = '.wrap' if captured_dict['W'] else '.clamp'
    hl = '.hi' if captured_dict['HI'] else '.lo'
    type_str = '.s64' if 'S' in captured_dict['type'] else '.b64'
    cd = captured_dict.copy()
    cd['type'] = ''
    d = ptx_r(kernel, cd, instr, 'rd')
    alo = ptx_r(kernel, cd, instr, 'ra')
    n = ptx_irc(kernel, cd, instr, 'pim', 'rb')
    ahi = ptx_irc(kernel, cd, instr, 'pim2', 'rc')

    if (('.hi' == hl and '.l' == lr) or ('.lo' == hl and '.r' == lr)) and 'b' in type_str:
        instr.add_ptx('shf', f'{lr}{mode}.b32 {d}, {alo}, {ahi}, {n};')
    else:
        if mode == '.warp':
            n_w = ptx_new_reg(kernel)
            instr.add_ptx('and', f'.b32 {n_w}, {n}')
            n = n_w
        a = ptx_pack(kernel, instr, alo, ahi)
        d64 = ptx_new_reg64(kernel)
        d2 = ptx_new_reg(kernel)
        if '.r' == lr and '.hi' == hl:
            instr.add_ptx('shr', f'{type_str} {d64}, {a}, {n};')
            ptx_unpack(instr, d2, d, d64)
        elif '.l' == lr and '.lo' == hl:
            instr.add_ptx('shl', f'{type_str} {d64}, {a}, {n};')
            ptx_unpack(instr, d, d2, d64)
        else:
            instr.ptx = None


def ptx_sgxt(kernel, captured_dict, instr):  # perfect
    mode = '.wrap' if captured_dict['W'] else '.clamp'
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_i(captured_dict, 'pim')
    i = int(b, base=0)
    i = min(i, 32) if mode == '.clamp' else i & 0x1f
    if captured_dict['U32']:
        instr.add_ptx('and', f'.b32 {d}, {a}, {2 ** i - 1:#0x};')
    else:
        instr.add_ptx('shl', f'.b32 {d}, {a}, {32 - i};')
        instr.add_ptx('shr', f'.s32 {d}, {d}, {32 - i};')


def ptx_abs(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_rc(kernel, captured_dict, instr, 'ra')

    instr.add_ptx('abs', f'.s32 {d}, {a};')


def ptx_sub(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')

    instr.add_ptx('sub', f'.s32 {d}, {a}, {b};')


def ptx_sub2(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')

    instr.add_ptx('sub', f'.s32 {d}, {b}, {a};')


def ptx_iadd3(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_r(kernel, captured_dict, instr, 'rc')
    cc1 = ptx_p(captured_dict, 'pcc1')
    cc2 = ptx_p(captured_dict, 'pcc2')
    x1 = ptx_p(captured_dict, 'px1')
    x2 = ptx_p(captured_dict, 'px2')

    if cc1 and cc1 != '0':
        type1 = '.s64'
        a64 = ptx_pack(kernel, instr, a, 0)
        b64 = ptx_pack(kernel, instr, b, 0)
        ab64 = ptx_new_reg64(kernel)
        instr.add_ptx('add', f'{type1} {ab64}, {a64}, {b64};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            x1_64 = ptx_pack(kernel, instr, f'{x1_t.replace("p", "x")}{x1_ord}', 0)
            instr.add_ptx('add', f'{type1} {ab64}, {ab64}, {x1_64};')
        ab = ptx_new_reg(kernel)
        cc1_t, cc1_ord = ptx_ord(cc1)
        if 'u' in cc1_t:
            kernel.upred_regs.add(cc1_ord)
        else:
            kernel.pred_regs.add(cc1_ord)
        ptx_unpack(instr, ab, f'{cc1_t.replace("p", "x")}{cc1_ord}', ab64)
    else:
        type1 = '.s32'
        ab = ptx_new_reg(kernel)
        instr.add_ptx('add', f'{type1} {ab}, {a}, {b};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            instr.add_ptx('add', f'{type1} {ab}, {ab}, {x1_t.replace("p", "x")}{x1_ord};')

    if cc2 and cc2 != '0':
        type2 = '.s64'
        c64 = ptx_pack(kernel, instr, c, 0)
        ab64 = ptx_pack(kernel, instr, ab, 0)
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('add', f'{type2} {d64}, {ab64}, {c64};')
        if x2 and x2 != '0':
            x2_t, x2_ord = ptx_ord(x2)
            x2_64 = ptx_pack(kernel, instr, f'{x2_t.replace("p", "x")}{x2_ord}', 0)
            instr.add_ptx('add', f'{type1} {d64}, {d64}, {x2_64};')
        cc2_t, cc2_ord = ptx_ord(cc2)
        if 'u' in cc2_t:
            kernel.upred_regs.add(cc2_ord)
        else:
            kernel.pred_regs.add(cc2_ord)
        ptx_unpack(instr, d, f'{cc2_t.replace("p", "x")}{cc2_ord}', d64)
    else:
        type2 = '.s32'
        instr.add_ptx('add', f'{type2} {d}, {ab}, {c};')
        if x2 and x2 != '0':
            x2_t, x2_ord = ptx_ord(x2)
            instr.add_ptx('add', f'{type1} {d}, {d}, {x2_t.replace("p", "x")}{x2_ord};')


def ptx_imad(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_r(kernel, captured_dict, instr, 'rc')
    # cc1 = ptx_p(captured_dict, 'pcc1')
    x1 = ptx_p(captured_dict, 'px1')
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    flag = '.lo'
    if captured_dict['type'] and captured_dict['type'] in ['.WIDE', '.HI']:
        flag = captured_dict['type'].lower()

    # if cc1 and cc1 != '0':
    #     type1 = '.s64'
    #     a64 = ptx_pack(kernel, instr, a, 0)
    #     b64 = ptx_pack(kernel, instr, b, 0)
    #     ab64 = ptx_new_reg64(kernel)
    #     instr.add_ptx('add', f'{type1} {ab64}, {a64}, {b64};')
    #     if x1 and x1 != '0':
    #         x1_ord = captured_dict['px1ord']
    #         x1_64 = ptx_pack(kernel, instr, f'%x{x1_ord}', 0)
    #         instr.add_ptx('add', f'{type1} {ab64}, {ab64}, {x1_64};')
    #     ab = ptx_new_reg(kernel)
    #     cc1_ord = captured_dict['pcc1ord']
    #     kernel.pred_regs.add(cc1_ord)
    #     ptx_unpack(instr, ab, f'%x{cc1_ord}', ab64)
    # else:
    if '.lo' == flag:
        instr.add_ptx('mad', f'.lo{type_str} {d}, {a}, {b}, {c};')
        # t = ptx_new_reg(kernel)
        # instr.add_ptx('mul', f'.lo{type_str} {t}, {a}, {b};')
        # instr.add_ptx('add', f'{type_str} {d}, {t}, {c};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            instr.add_ptx('add', f'{type_str} {d}, {d}, {x1_t.replace("p", "x")}{x1_ord};')
    else:
        c64 = ptx_r2d(kernel, instr, c) if 'r' in c else c
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('mul', f'.wide{type_str} {d64}, {a}, {b};')
        instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {c64};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            x1_64 = ptx_pack(kernel, instr, f'{x1_t.replace("p", "x")}{x1_ord}', 0)
            instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {x1_64};')
        d_t, d_ord = ptx_ord(d)
        if '.wide' == flag:
            ptx_unpack(instr, d, f'{d_t}{d_ord + 1}', d64)
        else:
            ptx_unpack(instr, ptx_new_reg(kernel), d, d64)


def ptx_imad2(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_r(kernel, captured_dict, instr, 'rb')
    x1 = ptx_p(captured_dict, 'px1')
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    flag = '.lo'
    if captured_dict['type'] and captured_dict['type'] in ['.WIDE', '.HI']:
        flag = captured_dict['type'].lower()
    cd = captured_dict.copy()
    if '.lo' != flag:
        cd['type'] = '64'
    c = ptx_irc(kernel, cd, instr, 'pim', 'rc')

    if '.lo' == flag:
        instr.add_ptx('mad', f'.lo{type_str} {d}, {a}, {b}, {c};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            instr.add_ptx('add', f'{type_str} {d}, {d}, {x1_t.replace("p", "x")}{x1_ord};')
    else:
        d64 = ptx_new_reg64(kernel)
        # instr.add_ptx('mad', f'.wide{type_str} {d64}, {a}, {b}, {c};')
        instr.add_ptx('mul', f'.wide{type_str} {d64}, {a}, {b};')
        instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {c};')
        if x1 and x1 != '0':
            x1_t, x1_ord = ptx_ord(x1)
            x1_64 = ptx_pack(kernel, instr, f'{x1_t.replace("p", "x")}{x1_ord}', 0)
            instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {x1_64};')
        d_t, d_ord = ptx_ord(d)
        if '.wide' == flag:
            ptx_unpack(instr, d, f'{d_t}{d_ord + 1}', d64)
        else:
            ptx_unpack(instr, ptx_new_reg(kernel), d, d64)


def ptx_shfl(kernel, captured_dict, instr):
    p = ptx_p(captured_dict, 'pp')
    if 'p' not in p:
        p = ''
    else:
        p = f'|{p}'
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_ir(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_ir(kernel, captured_dict, instr, 'imask', 'rc')
    mode = captured_dict["mode"].lower()
    instr.add_ptx('shfl', f'.sync.{mode}.b32 {d}{p}, {a}, {b}, {c}, -1;')


def ptx_sel(kernel, captured_dict, instr):
    type_str = '.f32' if instr.op == 'FSEL' else '.b32'
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_p(captured_dict, 'pc')
    instr.add_ptx('selp', f'{type_str} {d}, {a}, {b}, {c};')


def ptx_imnmx(kernel, captured_dict, instr):
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_p(captured_dict, 'pc')
    if '!' in c or '0' == c:
        instr.add_ptx('max', f'{type_str} {d}, {a}, {b};')
    else:
        instr.add_ptx('min', f'{type_str} {d}, {a}, {b};')


def ptx_prmt(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_ir(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_rc(kernel, captured_dict, instr, 'rc')
    mode = '' if not captured_dict['prmt'] else f'.{captured_dict["prmt"].lower()}'
    instr.add_ptx('prmt', f'.b32{mode} {d}, {a}, {c}, {b};')


def ptx_atom(kernel, captured_dict, instr):
    if instr.op == 'ATOMS':
        ss = '.shared'
    else:
        ss = '.global'
    op_str = captured_dict['op'].lower()
    if not captured_dict['type']:
        if op_str in ['or', 'and', 'xor']:
            type_str = '.b32'
        else:
            type_str = '.u32'
    else:
        type_str = captured_dict['type'].lower()
    if '64' in type_str and op_str == 'exch':
        type_str = '.b64'

    b = ptx_r(kernel, captured_dict, instr, 'rb')
    c = ptx_r(kernel, captured_dict, instr, 'rc')

    if c:
        c = f', {c}'
    else:
        c = ''

    adr = ptx_addr(kernel, captured_dict, instr)

    d = ptx_r(kernel, captured_dict, instr, 'rd')

    if d in ['', '0']:
        instr.add_ptx('red', f'{ss}{op_str}{type_str} {adr}, {b};')
    else:
        if '64' in type_str:
            d64 = ptx_new_reg64(kernel)
            instr.add_ptx('atom', f'{ss}{op_str}{type_str} {d64}, {adr}, {b}{c};')
            d_t, d_idx = ptx_ord(d)
            ptx_unpack(instr, f'{d_t}{d_idx}', f'{d_t}{d_idx + 1}', d64)
        else:
            instr.add_ptx('atom', f'{ss}{op_str}{type_str} {d}, {adr}, {b}{c};')


def ptx_lea(kernel, captured_dict, instr):
    hi = captured_dict['HI'].lower() if captured_dict['HI'] else ''
    x = captured_dict['X'].lower() if captured_dict['X'] else ''
    sx32 = captured_dict['SX32'].lower() if captured_dict['SX32'] else ''

    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_r(kernel, captured_dict, instr, 'rc')
    i = ptx_i(captured_dict, 'puim')
    cc = ptx_p(captured_dict, 'pcc1')
    xx = ptx_p(captured_dict, 'px1')

    if (not x) and (not hi) and (not sx32) and cc and (not xx):
        # LEA
        t = ptx_new_reg(kernel)
        instr.add_ptx('shl', f'.b32 {t}, {a}, {i};')
        a64 = ptx_pack(kernel, instr, t, 0)
        b64 = ptx_pack(kernel, instr, b, 0)
        instr.add_ptx('add', f'.s64 {b64}, {b64}, {a64};')
        cc1_t, cc1_ord = ptx_ord(cc)
        if 'u' in cc1_t:
            kernel.upred_regs.add(cc1_ord)
        else:
            kernel.pred_regs.add(cc1_ord)
        ptx_unpack(instr, d, f'{cc1_t.replace("p", "x")}{cc1_ord}', b64)
    elif hi and (not cc):
        if sx32:
            # LEA.HI.X.SX32
            a64 = ptx_new_reg64(kernel)
            instr.add_ptx('cvt', f'.s64.s32 {a64}, {a};')
        else:
            # LEA.HI.X
            a64 = ptx_pack(kernel, instr, a, c)
        instr.add_ptx('shl', f'.b64 {a64}, {a64}, {i};')
        b64 = ptx_pack(kernel, instr, 0, b)
        instr.add_ptx('add', f'.s64 {b64}, {b64}, {a64};')
        ptx_unpack(instr, ptx_new_reg(kernel), d, b64)
        if x and xx:
            x1_t, x1_ord = ptx_ord(xx)
            instr.add_ptx('add', f'.s32 {d}, {d}, {x1_t.replace("p", "x")}{x1_ord};')
    else:
        instr.ptx = None


def ptx_rcp(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')

    instr.add_ptx('rcp', f'.approx.ftz.f32 {d}, {a};')


def ptx_i2f(kernel, captured_dict, instr):
    rnd_s = captured_dict['rnd'].lower() if captured_dict['rnd'] else ''
    type_s = captured_dict['type'].lower() if captured_dict['type'] else '.s32'
    f64_s = captured_dict['F64'].lower() if captured_dict['F64'] else '.f32'

    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_irc(kernel, captured_dict, instr, 'pim', 'ra')

    if f64_s == '.f64':
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('cvt', f'{rnd_s}{f64_s}{type_s} {d64}, {a};')
        d_t, d_ord = ptx_ord(d)
        ptx_unpack(instr, d, f'{d_t}{d_ord + 1}', d64)
    else:
        instr.add_ptx('cvt', f'{rnd_s}{f64_s}{type_s} {d}, {a};')


def ptx_f2i(kernel, captured_dict, instr):
    rnd_s = captured_dict['round'].lower() if captured_dict['round'] else ''
    ntz_s = captured_dict['NTZ'].lower() if captured_dict['NTZ'] else ''
    ftz_s = captured_dict['FTZ'].lower() if captured_dict['FTZ'] else ''
    type_s = captured_dict['type'].lower() if captured_dict['type'] else '.s32'
    f64_s = captured_dict['F64'].lower() if captured_dict['F64'] else '.f32'

    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_irc(kernel, captured_dict, instr, 'pim', 'ra')

    if ftz_s and (type_s == '.u32') and (rnd_s == '.trunc') and ntz_s:
        instr.add_ptx('cvt', f'.rzi.ftz{type_s}.f32 {d}, {a};')
    else:
        instr.ptx = None


def ptx_bar(kernel, captured_dict, instr):
    i = ptx_i(captured_dict, 'pim')
    instr.add_ptx('bar', f'.sync {i};')


def ptx_plop3(kernel, captured_dict, instr):
    p = ptx_p(captured_dict, 'pp')
    i = ptx_i(captured_dict, 'pim')
    if i == '0x80':
        instr.add_ptx('not', f'.pred {pp}, 0;')
    elif i == '0x8':
        instr.add_ptx('not', f'.pred {pp}, 1;')


def ptx_popc(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')

    instr.add_ptx('popc', f'.b32 {d}, {a};')


def ptx_flo(kernel, captured_dict, instr):
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    sh = '.shiftamt' if captured_dict['SH'] else ''
    d = ptx_r(kernel, captured_dict, instr, 'rd')
    a = ptx_r(kernel, captured_dict, instr, 'ra')

    instr.add_ptx('bfind', f'{sh}{type_str} {d}, {a};')


def ptx_vote(kernel, captured_dict, instr):
    d = ptx_r(kernel, captured_dict, instr, 'rd')

    instr.add_ptx('vote', f'.sync.ballot.b32 {d}, 1, 0xffffffff;')


grammar_ptx = {
    # Floating Point Instructions
    'FADD': [],  # FP32 Add
    'FADD32I': [],  # FP32 Add
    'FCHK': [],  # Floating-point Range Check
    'FFMA32I': [],  # FP32 Fused Multiply and Add
    'FFMA': [],  # FP32 Fused Multiply and Add
    'FMNMX': [],  # FP32 Minimum/Maximum
    'FMUL': [],  # FP32 Multiply
    'FMUL32I': [],  # FP32 Multiply
    'FSEL': [  # Floating Point Select
        {'rule': rf'FSEL {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {pc};', 'ptx': ptx_sel}
    ],
    'FSET': [],  # FP32 Compare And Set
    'FSETP': [],  # FP32 Compare And Set Predicate
    'FSWZADD': [],  # FP32 Swizzle Add
    'MUFU': [  # FP32 Multi Function Operation
        {'rule': rf'MUFU\.RCP {rd}, {ra};', 'ptx': ptx_rcp}
    ],
    'HADD2': [],  # FP16 Add
    'HADD2_32I': [],  # FP16 Add
    'HFMA2': [],  # FP16 Fused Mutiply Add
    'HFMA2_32I': [],  # FP16 Fused Mutiply Add
    'HMMA': [],  # Matrix Multiply and Accumulate
    'HMNMX2': [],  # FP16 Minimum / Maximum
    'HMUL2': [],  # FP16 Multiply
    'HMUL2_32I': [],  # FP16 Multiply
    'HSET2': [],  # FP16 Compare And Set
    'HSETP2': [],  # FP16 Compare And Set Predicate
    'DADD': [],  # FP64 Add
    'DFMA': [],  # FP64 Fused Mutiply Add
    'DMMA': [],  # Matrix Multiply and Accumulate
    'DMUL': [],  # FP64 Multiply
    'DSETP': [],  # FP64 Compare And Set Predicate

    # Integer Instructions
    'BMMA': [],  # Bit Matrix Multiply and Accumulate
    'BMSK': [  # Bitfield Mask
    ],
    'BREV': [],  # Bit Reverse
    'FLO': [  # Find Leading One
        {'rule': rf'FLO{u32}{tsh} {rd}, {ra};', 'ptx': ptx_flo},
    ],
    'IABS': [  # Integer Absolute Value
        {'rule': rf'IABS {rd}, (?:{ra}|{pim}|{caddr});', 'ptx': ptx_abs},
    ],
    'IADD': [],  # Integer Addition
    'IADD3': [  # 3-input Integer Addition
        {'rule': rf'IADD3 {rd}, {ra}, -(?:{rb}|{pim}|{caddr}), RZ;', 'ptx': ptx_sub},
        {'rule': rf'IADD3 {rd}, -{ra}, (?:{rb}|{pim}|{caddr}), RZ;', 'ptx': ptx_sub2},
        {'rule': rf'IADD3{X} {rd}, ({pcc1}, )?({pcc2}, )?{ra}, (?:{rb}|{pim}|{caddr}),'
                 rf' {rc}(, {px1})?(, {px2})?;', 'ptx': ptx_iadd3},
    ],
    'IADD32I': [],  # Integer Addition
    'IDP': [],  # Integer Dot Product and Accumulate
    'IDP4A': [],  # Integer Dot Product and Accumulate
    'IMAD': [  # Integer Multiply And Add
        {'rule': rf'IMAD\.MOV{u32} {rd}, RZ, RZ, (?:{pim}|{ra}|{caddr});', 'ptx': ptx_mov},
        {'rule': rf'IMAD{timad}{u32}{X} {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc}(, {px1})?;',
         'ptx': ptx_imad},
        {'rule': rf'IMAD{timad}{u32}{X} {rd}, {ra}, {rb}, (?:{rc}|{pim}|{caddr})(, {px1})?;',
         'ptx': ptx_imad2},
    ],
    'IMMA': [  # Integer Matrix Multiply and Accumulate
    ],
    'IMNMX': [  # Integer Minimum/Maximum
        {'rule': rf'IMNMX{u32} {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {pc};', 'ptx': ptx_imnmx}
    ],
    'IMUL': [],  # Integer Multiply
    'IMUL32I': [],  # Integer Multiply
    'ISCADD': [],  # Scaled Integer Addition
    'ISCADD32I': [],  # Scaled Integer Addition
    'ISETP': [  # Integer Compare And Set Predicate
        {'rule': rf'ISETP{ticmp}{u32}{tbool}{tex} {pp}, {pq}, {ra},'
                 rf' (?:{rb}|{pim}|{caddr}), {pc}(, {px1})?;',
         'ptx': ptx_isetp}
    ],
    'LEA': [  # LOAD Effective Address
        {'rule': rf'LEA{thi}{X}{tsx32} {rd}, ({pcc1}, )?{ra}, (?:{rb}|{pim}|{caddr}), ({rc}, )?{puim}(, {px1})?;',
         'ptx': ptx_lea}
    ],
    'LOP': [],  # Logic Operation
    'LOP3': [  # Logic Operation
        {'rule': rf'LOP3\.LUT{tpand} ({pp}, )?{rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc}, {imlut}, {pc};',
         'ptx': ptx_lop3},
    ],
    'LOP32I': [],  # Logic Operation
    'POPC': [  # Population count
        {'rule': rf'POPC {rd}, {ra};', 'ptx': ptx_popc},
    ],
    'SHF': [  # Funnel Shift
        {'rule': rf'SHF{tshf_lr}{tw}{tshf_type} {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc};', 'ptx': ptx_shf},
        {'rule': rf'SHF{tshf_lr}{tw}{tshf_type} {rd}, {ra}, {rb}, (?:{rc}|{pim}|{caddr});', 'ptx': ptx_shf},
    ],
    'SHL': [],  # Shift Left
    'SHR': [],  # Shift Right
    'VABSDIFF': [],  # Absolute Difference
    'VABSDIFF4': [],  # Absolute Difference

    # Conversion Instructions
    'F2F': [],  # Floating Point To Floating Point Conversion
    'F2I': [  # Floating Point To Integer Conversion
        {'rule': rf'F2I{tftz}{tx2x}{tround} {rd}, (?:{ra}|{pim}|{caddr});', 'ptx': ptx_f2i},
    ],
    'I2F': [  # Integer To Floating Point Conversion
        {'rule': rf'I2F{tx2x}{trnd} {rd}, (?:{ra}|{pim}|{caddr});', 'ptx': ptx_i2f},
    ],
    'I2I': [],  # Integer To Integer Conversion
    'I2IP': [],  # Integer To Integer Conversion and Packing
    'FRND': [],  # Round To Integer

    # Movement Instructions
    'MOV': [  # Move
        {'rule': rf'MOV {rd}, (?:{pim}|{ra}|{caddr}|{GLOBAL_NAME_RE});', 'ptx': ptx_mov},
    ],
    'MOV32I': [],  # Move
    'MOVM': [],  # Move Matrix with Transposition or Expansion
    'PRMT': [  # Permute Register Pair
        {'rule': rf'PRMT{tprmt} {rd}, {ra}, (?:{rb}|{pim}), (?:{rc}|{caddr});', 'ptx': ptx_prmt}
    ],
    'SEL': [  # Select Source with Predicate
        {'rule': rf'SEL {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {pc};', 'ptx': ptx_sel}
    ],
    'SGXT': [  # Sign Extend
        {'rule': rf'SGXT{tw}{u32} {rd}, {ra}, {pim};', 'ptx': ptx_sgxt}
    ],
    'SHFL': [  # Warp Wide Register Shuffle
        {'rule': rf'SHFL{shfl} {pp}, {rd}, {ra}, (?:{pim}|{rb}), (?:{imask}|{rc});', 'ptx': ptx_shfl}
    ],

    # Predicate Instructions
    'PLOP3': [  # Predicate Logic Operation
        {'rule': rf'PLOP3\.LUT {pp}, PT, PT, PT, PT, {pim}, 0x0;',
         'ptx': ptx_plop3},
    ],
    'PSETP': [],  # Combine Predicates and Set Predicate
    'P2R': [  # Move Predicate Register To Register
    ],
    'R2P': [],  # Move Register To Predicate Register

    # Load/Store Instructions
    'LD': [  # Load from generic Memory
    ],
    'LDC': [  # Load Constant
        {'rule': rf'LDC{tmem_type}{tldc_isl} {rd}, {caddr};', 'ptx': ptx_ldst},
    ],
    'LDG': [  # Load from Global Memory
        {'rule': rf'LDG{te}{tmem_cache}{tmem_ltc}{tmem_type}{tmem_scopes}{tzd} {rd}, {paddr};', 'ptx': ptx_ldst}
    ],
    'LDGDEPBAR': [],  # Global Load Dependency Barrier
    'LDGSTS': [],  # Asynchronous Global to Shared Memcopy
    'LDL': [  # Load within Local Memory Window
        {'rule': rf'LDL{tmem_cache}{tmem_type} {rd}, {paddr};', 'ptx': ptx_ldst}
    ],
    'LDS': [  # Load within Shared Memory Window
        {'rule': rf'LDS{tu}{tmem_type}{tzd} {rd}, {paddr};', 'ptx': ptx_ldst}
    ],
    'LDSM': [],  # Load Matrix from Shared Memory with Element Size Expansion
    'ST': [
    ],  # Store to Generic Memory
    'STG': [  # Store to Global Memory
        {'rule': rf'STG{te}{tmem_cache}{tmem_type}{tmem_scopes}{tzd} {paddr}, {rc};', 'ptx': ptx_ldst}
    ],
    'STL': [  # Store within Local or Shared Window
        {'rule': rf'STL{tmem_cache}{tmem_type} {paddr}, {rc};', 'ptx': ptx_ldst}
    ],
    'STS': [  # Store within Local or Shared Window
        {'rule': rf'STS{tmem_type} {paddr}, {rc};', 'ptx': ptx_ldst}
    ],
    'MATCH': [],  # Match Register Values Across Thread Group
    'QSPC': [],  # Query Space
    'ATOM': [
    ],  # Atomic Operation on Generic Memory
    'ATOMS': [  # Atomic Operation on Shared Memory
        {'rule': rf'ATOMS{tatom_op}{tmem_type}'
                 rf' {rd}, {paddr}(, {rb})?(, {rc})?;', 'ptx': ptx_atom},
    ],
    'ATOMG': [  # Atomic Operation on Global Memory
        {'rule': rf'ATOMG{te}{tatom_op}{tmem_cache}{tmem_type}{tmem_scopes}'
                 rf' ({pp}, )?{rd}, {paddr}, {rb}(, {rc})?;', 'ptx': ptx_atom},
    ],
    'RED': [  # Reduction Operation on Generic Memory
        {'rule': rf'RED{te}{tatom_op}{tmem_cache}{tmem_type}{tmem_scopes}'
                 rf' {paddr}, {rb};', 'ptx': ptx_atom},
    ],
    'CCTL': [],  # Cache Control
    'CCTLL': [],  # Cache Control
    'ERRBAR': [],  # Error Barrier
    'MEMBAR': [],  # Memory Barrier
    'CCTLT': [],  # Texture Cache Control

    # Uniform Datapath Instructions
    'R2UR': [  # Move from Vector Register to a Uniform Register
    ],
    'REDUX': [],  # Reduction of a Vector Register into a Uniform Register
    'S2UR': [  # Move Special Register to Uniform Register
        {'rule': rf'S2UR {rd}, {sr};', 'ptx': ptx_s2r}
    ],
    'UBMSK': [],  # Uniform Bitfield Mask
    'UBREV': [],  # Uniform Bit Reverse
    'UCLEA': [],  # Load Effective Address for a Constant
    'UFLO': [  # Uniform Find Leading One
    ],
    'UIADD3': [  # Uniform Integer Addition
        {'rule': rf'UIADD3 {rd}, {ra}, -(?:{rb}|{pim}|{caddr}), URZ;', 'ptx': ptx_sub},
        {'rule': rf'UIADD3 {rd}, -{ra}, (?:{rb}|{pim}|{caddr}), URZ;', 'ptx': ptx_sub2},
        {'rule': rf'UIADD3{X} {rd}, ({pcc1}, )?({pcc2}, )?{ra}, (?:{rb}|{pim}|{caddr}),'
                 rf' {rc}(, {px1})?(, {px2})?;', 'ptx': ptx_iadd3}
    ],
    'UIMAD': [  # Uniform Integer Multiplication
        {'rule': rf'UIMAD\.MOV{u32} {rd}, RZ, RZ, (?:{pim}|{ra}|{caddr});', 'ptx': ptx_mov},
        {'rule': rf'UIMAD{timad}{u32}{X} {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc}(, {px1})?;',
         'ptx': ptx_imad},
        {'rule': rf'UIMAD{timad}{u32}{X} {rd}, {ra}, {rb}, (?:{rc}|{pim}|{caddr})(, {px1})?;',
         'ptx': ptx_imad2},
    ],
    'UISETP': [  # Integer Compare and Set Uniform Predicate
        {'rule': rf'UISETP{ticmp}{u32}{tbool}{tex} {pp}, {pq}, {ra},'
                 rf' (?:{rb}|{pim}|{caddr}), {pc}(, {px1})?;',
         'ptx': ptx_isetp}
    ],
    'ULDC': [  # Load from Constant Memory into a Uniform Register
        {'rule': rf'ULDC{tmem_type} {rd}, {caddr};', 'ptx': ptx_ldst}
    ],
    'ULEA': [  # Uniform Load Effective Address
        {'rule': rf'ULEA{thi}{X}{tsx32} {rd}, ({pcc1}, )?{ra}, (?:{rb}|{pim}|{caddr}), ({rc}, )?{puim}(, {px1})?;',
         'ptx': ptx_lea}
    ],
    'ULOP': [],  # Logic Operation
    'ULOP3': [  # Logic Operation
        {'rule': rf'ULOP3\.LUT{tpand} ({pp}, )?{rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc}, {imlut}, {pc};',
         'ptx': ptx_lop3},
    ],
    'ULOP32I': [],  # Logic Operation
    'UMOV': [  # Uniform Move
        {'rule': rf'UMOV {rd}, (?:{pim}|{ra}|{caddr}|{GLOBAL_NAME_RE});', 'ptx': ptx_mov},
    ],
    'UP2UR': [],  # Uniform Predicate to Uniform Register
    'UPLOP3': [],  # Uniform Predicate Logic Operation
    'UPOPC': [  # Uniform Population Count
        {'rule': rf'UPOPC {rd}, {ra};', 'ptx': ptx_popc},
    ],
    'UPRMT': [  # Uniform Byte Permute
    ],
    'UPSETP': [],  # Uniform Predicate Logic Operation
    'UR2UP': [],  # Uniform Register to Uniform Predicate
    'USEL': [  # Uniform Select
        {'rule': rf'USEL {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {pc};', 'ptx': ptx_sel}
    ],
    'USGXT': [],  # Uniform Sign Extend
    'USHF': [  # Uniform Funnel Shift
        {'rule': rf'USHF{tshf_lr}{tw}{tshf_type} {rd}, {ra}, (?:{rb}|{pim}|{caddr}), {rc};', 'ptx': ptx_shf},
        {'rule': rf'USHF{tshf_lr}{tw}{tshf_type} {rd}, {ra}, {rb}, (?:{rc}|{pim2}|{caddr});', 'ptx': ptx_shf},
    ],
    'USHL': [],  # Uniform Left Shift
    'USHR': [],  # Uniform Right Shift
    'VOTEU': [  # Voting across SIMD Thread Group with Results in Uniform Destination
        {'rule': rf'VOTEU\.ALL {rd}, UPT, PT;', 'ptx': ptx_vote}
    ],

    # Texture Instructions
    'TEX': [],  # Texture Fetch
    'TLD': [],  # Texture Load
    'TLD4': [],  # Texture Load 4
    'TMML': [],  # Texture MipMap Level
    'TXD': [],  # Texture Fetch With Derivatives
    'TXQ': [],  # Texture Query

    # Surface Instructions
    'SUATOM': [],  # Atomic Op on Surface Memory
    'SULD': [],  # Surface Load
    'SURED': [],  # Reduction Op on Surface Memory
    'SUST': [],  # Surface Store

    # Control Instructions
    'BMOV': [  # Move Convergence Barrier State
    ],
    'BPT': [],  # BreakPoint/Trap
    'BRA': [  # Relative Branch
        {'rule': rf'BRA(?P<U>\.U)? `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_bra}
    ],
    'BREAK': [  # Break out of the Specified Convergence Barrier
    ],
    'BRX': [  # Relative Branch Indirect
    ],
    'BRXU': [],  # Relative Branch with Uniform Register Based Offset
    'BSSY': [  # Barrier Set Convergence Synchronization Point
    ],
    'BSYNC': [  # Synchronize Threads on a Convergence Barrier
    ],
    'CALL': [  # Call Function
    ],
    'EXIT': [  # Exit Program
        {'rule': rf'EXIT;', 'ptx': ptx_exit}
    ],
    'JMP': [],  # Absolute Jump
    'JMX': [],  # Absolute Jump Indirect
    'JMXU': [],  # Absolute Jump with Uniform Register Based Offset
    'KILL': [],  # Kill Thread
    'NANOSLEEP': [],  # Suspend Execution
    'RET': [  # Return From Subroutine
    ],
    'RPCMOV': [],  # PC Register Move
    'RTT': [],  # Return From Trap
    'WARPSYNC': [  # Synchronize Threads in Warp
    ],
    'YIELD': [  # Yield Control
    ],

    # Miscellaneous Instructions
    'B2R': [],  # Move Barrier To Register
    'BAR': [  # Barrier Synchronization
        {'rule': rf'BAR\.SYNC {pim};', 'ptx': ptx_bar}
    ],
    'CS2R': [  # Move Special Register to Register
        {'rule': rf'CS2R{tcs2r} {rd}, {sr};', 'ptx': ptx_s2r}
    ],
    'DEPBAR': [  # Dependency Barrier
    ],
    'GETLMEMBASE': [],  # Get Local Memory Base Address
    'LEPC': [],  # Load Effective PC
    'NOP': [  # No Operation
    ],
    'PMTRIG': [],  # Performance Monitor Trigger
    'R2B': [],  # Move Register to Barrier
    'S2R': [  # Move Special Register to Register
        {'rule': rf'S2R {rd}, {sr};', 'ptx': ptx_s2r}
    ],
    'SETCTAID': [],  # Set CTA ID
    'SETLMEMBASE': [],  # Set Local Memory Base Address
    'VOTE': [  # Vote Across SIMD Thread Group
        {'rule': rf'VOTE\.ALL {rd}, PT, PT;', 'ptx': ptx_vote}
    ],

}

# def ptx_add(f, d, a, b):
#     if '-' in a:
#         op = 'sub'
#         rest = f'{f}.s32 {d}, {b}, {a.strip("-")};'
#     elif '-' in b:
#         op = 'sub'
#         rest = f'{f}.s32 {d}, {a}, {b.strip("-")};'
#     else:
#         op = 'add'
#         rest = f'{f}.s32 {d}, {a}, {b};'
#     return op, rest
#
#
# def ptx_find_x(kernel, instr):
#     line_num = instr['line_num']
#     instr_x = None
#     for n_instr in kernel.instrs[line_num + 1:]:
#         rest = n_instr['rest']
#         m = re.search(rf'\.X[. ]', rest)
#         if m and n_instr['line_num'] and n_instr['line_num'] >= 0:
#             instr_x = n_instr
#             break
#     return instr_x
#
#
# def ptx_bfe(kernel, instrs, captured_dict, instr):
#     type_str = 'u32' if captured_dict['U32'] else 's32'
#     d = ptx_r(captured_dict, 'r0')
#     a = ptx_r(captured_dict, 'r8')
#     b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
#     if '%r' in b:
#         r_idx = kernel.reg_count + 256
#         c = f'%r{r_idx}'
#         kernel.reg_set.add(r_idx)
#         kernel.ptx_reg_count += 1
#         ptx_append_instr(instrs, instr, 'shr', f'.{type_str} {c}, {b}, 8;')
#     else:
#         b = int(b, base=0)
#         c = b >> 8
#         b = b & 0xff
#
#     instr['op'] = 'bfe'
#     instr['rest'] = f'.{type_str} {d}, {a}, {b}, {c};'
#
#
# def ptx_bfi(kernel, instrs, captured_dict, instr):
#     d = ptx_r(captured_dict, 'r0')
#     a = ptx_r(captured_dict, 'r8')
#     b = ptx_ir(captured_dict, 'i20', 'r20')
#     e = ptx_irc(kernel, instrs, captured_dict, instr, 'ixx', 'r39')
#     if '%r' in b:
#         r_idx = kernel.reg_count + 256
#         c = f'%r{r_idx}'
#         kernel.reg_set.add(r_idx)
#         kernel.ptx_reg_count += 1
#         ptx_append_instr(instrs, instr, 'shr', f'.b32 {c}, {b}, 8;')
#     else:
#         b = int(b, base=0)
#         c = b >> 8
#         b = b & 0xff
#
#     instr['op'] = 'bfi'
#     instr['rest'] = f'.b32 {d}, {a}, {e}, {b}, {c};'
#
#
# def ptx_xmad(kernel, instrs, captured_dict, instr):
#     mode = captured_dict['mode']
#     line_num = instr['line_num']
#     a_full = captured_dict["a"]
#     if '.H1' in a_full:
#         a_full = a_full[:-3]
#     a = ptx_r(captured_dict, 'r8')
#     b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
#     b_full = captured_dict["b"]
#     b_full = b_full.replace('[', '\\[')
#     b_full = b_full.replace(']', '\\]')
#     b_full = b_full.replace('+', '\\+')
#     if '.H1' in b_full:
#         b_full = b_full[:-3]
#     c1 = c3 = c = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r39')
#     captured_dict1 = None
#     captured_dict2 = None
#     captured_dict3 = None
#     captured_dict_chi = None
#     captured_dict_mrg = None
#     captured_dict_l = None
#
#     if not mode:
#         if '.H1' in captured_dict['a']:
#             captured_dict3 = captured_dict
#             c3 = c
#         elif '.H1' in captured_dict['b']:
#             captured_dict2 = captured_dict
#         else:
#             captured_dict1 = captured_dict
#             c1 = c
#     elif mode == 'MRG':
#         captured_dict_mrg = captured_dict
#
#     for n_instr in kernel.instrs[line_num + 1:]:
#         statement = n_instr['op'] + n_instr['rest']
#         if m := re.search(rf'XMAD (?P<d>{r0}), {a_full}, {b_full}, (?P<c>(?:{r39}|{i20}|{CONST_NAME_RE}));', statement):
#             captured_dict1 = m.groupdict()
#             n_instr['line_num'] = None
#             c1 = ptx_irc(kernel, instrs, captured_dict1, instr, 'i20', 'r39')
#         elif m := re.search(rf'XMAD\.MRG (?P<d>{r0}), {a_full}, {b_full}\.H1, RZ;', statement):
#             captured_dict_mrg = m.groupdict()
#             n_instr['line_num'] = None
#         elif m := re.search(rf'XMAD\.CHI (?P<d>{r0}), {a_full}\.H1, {b_full},', statement):
#             captured_dict_chi = m.groupdict()
#             n_instr['line_num'] = None
#         elif m := re.search(rf'XMAD (?P<d>{r0}), {a_full}, {b_full}\.H1, RZ;', statement):
#             captured_dict2 = m.groupdict()
#             n_instr['line_num'] = None
#         elif m := re.search(rf'XMAD (?P<d>{r0}), {a_full}\.H1, {b_full}\.H1, (?P<c>(?:{r39}|{i20}|{CONST_NAME_RE}));',
#                             statement):
#             captured_dict3 = m.groupdict()
#             n_instr['line_num'] = None
#             c3 = ptx_irc(kernel, instrs, captured_dict3, instr, 'i20', 'r39')
#         elif captured_dict1 and (
#                 m := re.search(rf'XMAD\.PSL {r0}, {a_full}\.H1, {b_full}, {captured_dict1["d"]};', statement)):
#             captured_dict_l = m.groupdict()
#             n_instr['line_num'] = None
#             d = ptx_r(captured_dict_l, 'r0')
#             instr['op'] = 'mad'
#             instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
#             break
#         elif captured_dict_mrg and captured_dict1 and (m := re.search(
#                 rf'XMAD\.PSL\.CBCC {r0}, {a_full}\.H1, {captured_dict_mrg["d"]}\.H1, {captured_dict1["d"]};',
#                 statement)):
#             captured_dict_l = m.groupdict()
#             n_instr['line_num'] = None
#             d = ptx_r(captured_dict_l, 'r0')
#             instr['op'] = 'mad'
#             instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
#             break
#         elif captured_dict_chi and captured_dict2 and captured_dict3 and (m := re.search(
#                 rf'IADD3\.RS (?P<d>{r0}), {captured_dict_chi["d"]}, {captured_dict2["d"]}, {captured_dict3["d"]};',
#                 statement)):
#             captured_dict_l = m.groupdict()
#             n_instr['line_num'] = None
#             d = ptx_r(captured_dict_l, 'r0')
#             instr['op'] = 'mad'
#             instr['rest'] = f'.hi.u32 {d}, {a}, {b}, {c3};'
#             break
#     if not captured_dict_l:
#         if captured_dict1:
#             ptx_append_instr(instrs, instr, 'and', f'.b32 {a}, {a}, 0xffff;')
#             if '%r' in b:
#                 ptx_append_instr(instrs, instr, 'and', f'.b32 {b}, {b}, 0xffff;')
#             d = ptx_r(captured_dict1, 'r0')
#             instr['op'] = 'mad'
#             instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
#         else:
#             instr['line_num'] = -instr['line_num']
#
#
# def ptx_icmp(kernel, instrs, captured_dict, instr):
#     cmp_str = captured_dict['cmp'].lower()
#     type_str = 'u32' if captured_dict['U32'] else 's32'
#     d = ptx_r(captured_dict, 'r0')
#     a = ptx_r(captured_dict, 'r8')
#     b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
#     c = ptx_r(captured_dict, 'r39')
#
#     p_idx = kernel.ptx_pred_reg_count + 7
#     kernel.pred_regs.add(p_idx)
#     kernel.ptx_pred_reg_count += 1
#
#     ptx_append_instr(instrs, instr, 'setp', f'.{cmp_str}.{type_str} %p{p_idx}, {c}, 0;')
#
#     instr['op'] = 'selp'
#     instr['rest'] = f'.b32 {d}, {a}, {b}, %p{p_idx};'
#
#
# def ptx_lop(kernel, instrs, captured_dict, instr):
#     instr['op'] = captured_dict['bool'].lower()
#     d = ptx_r(captured_dict, 'r0')
#     a = ptx_r(captured_dict, 'r8')
#     if captured_dict['INV8']:
#         a = f'~{a}'
#     b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
#     if instr['op'] == 'pass_b':
#         instr['op'] = 'not'
#         instr['rest'] = f'.b32 {d}, {b};'
#     else:
#         if captured_dict['TINV']:
#             b = f'{~int(b, base=0)}'
#         elif captured_dict['INV']:
#             b = f'~{b}'
#         instr['rest'] = f'.b32 {d}, {a}, {b};'
#
#
# def ptx_psetp(kernel, instrs, captured_dict, instr):
#     bool_str = captured_dict['bool'].lower()
#     bool2_str = captured_dict['bool2'].lower()
#     p = ptx_p(captured_dict, 'p3')
#     q = ptx_p(captured_dict, 'p0')
#     a = ptx_p(captured_dict, 'p12')
#     b = ptx_p(captured_dict, 'p29')
#     c = ptx_p(captured_dict, 'p39')
#     a = a.replace('%pt', '1')
#     b = b.replace('%pt', '1')
#     c = c.replace('%pt', '1')
#     ptx_append_instr(instrs, instr, bool_str, f'.pred {p}, {a}, {b};')
#     if not ('1' == c and 'and' == bool_str):
#         ptx_append_instr(instrs, instr, bool2_str, f'.pred {p}, {p}, {c};')
#     if 'pt' not in q:
#         ptx_append_instr(instrs, instr, 'not', f'.pred {q}, {p};')
#     instr['line_num'] = None
#
#
# def ptx_lop32i(kernel, instrs, captured_dict, instr):
#     instr['op'] = captured_dict['bool2'].lower()
#     d = ptx_r(captured_dict, 'r0')
#     a = ptx_r(captured_dict, 'r8')
#     if captured_dict['INV8']:
#         a = f'~{a}'
#     b = ptx_i(captured_dict, 'i20w32')
#     rest = f'.b32 {d}, {a}, {b};'
#     instr['rest'] = rest
#
#
# def ptx_mov32i(kernel, instrs, captured_dict, instr):
#     instr['op'] = 'mov'
#     d = ptx_r(captured_dict, 'r0')
#     if 'i20w32' in captured_dict:
#         a = ptx_i(captured_dict, 'i20w32')
#         instr['rest'] = f'.b32 {d}, {a};'
#     else:
#         type_str = captured_dict['type']
#         line_num = instr['line_num']
#         instr_hi = None
#         for n_instr in kernel.instrs[line_num + 1:]:
#             rest = n_instr['rest']
#             m = re.search(rf'32@hi\({captured_dict["name"]}\)', rest)
#             if m and n_instr['line_num'] >= 0:
#                 instr_hi = n_instr
#                 instr_hi['line_num'] = None
#                 break
#         if 'lo' in type_str and instr_hi:
#             rd_idx = kernel.reg64_count
#             global_name = captured_dict['name']
#             ptx_append_instr(instrs, instr, 'mov', f'.u64 %dr{rd_idx}, {global_name};')
#             kernel.reg64_count += 1
#             d_idx = captured_dict['r0ord']
#             d = f'{{%r{d_idx}, %r{d_idx + 1}}}'
#             instr['rest'] = f'.b64 {d}, %dr{rd_idx};'
#         else:
#             instr['line_num'] = -instr['line_num']
#
#
# def ptx_sync(kernel, instrs, captured_dict, instr):
#     instr['op'] = 'bra'
#     instr['rest'] = f' {captured_dict["label"]};'
#
#
# def ptx_brk(kernel, instrs, captured_dict, instr):
#     instr['op'] = 'bra'
#     instr['rest'] = f' {captured_dict["label"]};'
#
#
# def ptx_bar(kernel, instrs, captured_dict, instr):
#     instr['op'] = 'bar'
#     if captured_dict['i8w8']:
#         i_str = ptx_i(captured_dict, 'i8w8')
#         instr['rest'] = f'.sync {i_str};'
#     else:
#         instr['rest'] = instr['rest'].lower()
#     pass
#
#
# def ptx_r2p(kernel, instrs, captured_dict, instr):
#     a = ptx_r(captured_dict, 'r8')
#     b = ptx_i(captured_dict, 'i20')
#     b = int(b, base=0) if b else 0
#     for i in range(7):
#         if b & (1 << i):
#             kernel.pred_regs.add(i)
#             r_idx = kernel.reg_count + 256
#             r_str = f'%r{r_idx}'
#             kernel.reg_set.add(r_idx)
#             kernel.ptx_reg_count += 1
#             ptx_append_instr(instrs, instr, 'and', f'.b32 {r_str}, {a}, {1 << i};')
#             ptx_append_instr(instrs, instr, 'setp', f'.eq.s32 %p{i}, {r_str}, 0;')
#     instr['line_num'] = None
#
#
# grammar_ptx_old = {
#     # Integer Instructions
#     'BFE': [
#         {'rule': rf'BFE{u32} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_bfe}],
#     'BFI': [
#         {'rule': rf'BFI {r0nc}, {r8}, (?:{r20}|{i20}), (?:{r39}|{CONST_NAME_RE});', 'ptx': ptx_bfi}],
#     'XMAD': [  # mad
#         {'rule': rf'XMAD{xmad} (?P<d>{r0nc}), (?P<a>{r8}), (?P<b>(?:{r20}|{i20}|{CONST_NAME_RE})), (?P<c>{r39});',
#          'ptx': ptx_xmad},
#         {'rule': rf'XMAD{xmad} (?P<d>{r0nc}), (?P<a>{r8}), (?P<b>{r20}), (?P<c>(?:{i20}|{CONST_NAME_RE}));',
#          'ptx': ptx_xmad}],
#
#     # Comparison and Selection Instructions
#     'ICMP': [  # slct
#         {'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_icmp}],
#     # Logic and Shift Instructions
#     'LOP': [  # and or xor not
#         {'rule': rf'LOP{bool_} {r0nc}, (?P<INV8>~)?{r8}, (?P<INV>~)?(?:{r20}|{i20}|{CONST_NAME_RE})(?P<TINV>\.INV)?;',
#          'ptx': ptx_lop}],
#     'LOP32I': [  # and or xor not
#         {'rule': rf'LOP32I{bool2} {r0nc}, (?P<INV8>~)?{r8}, {i20w32};', 'ptx': ptx_lop32i}],
#     # Movement Instructions
#     'MOV32I': [  # mov
#         {'rule': rf'MOV32I {r0nc}, {i20w32};', 'ptx': ptx_mov32i},
#         {'rule': rf'MOV32I {r0nc}, {GLOBAL_NAME_RE};', 'ptx': ptx_mov32i}],
#     # Predicate/CC Instructions
#     'PSETP': [  # setp
#         {'rule': rf'PSETP(?:\.(?P<bool>AND|OR|XOR)){bool2} {p3}, {p0}, {p12}, {p29}, {p39};', 'ptx': ptx_psetp}],

#     'BRK': [  # bra
#         {'rule': rf'BRK `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_brk}],
#     'SYNC': [  # bra
#         {'rule': rf'SYNC `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_sync}],
#
#     # Miscellaneous Instructions
#     'BAR': [  # bar
#         {'rule': rf'BAR\.SYNC (?:{i8w8}|{r8});', 'ptx': ptx_bar}],
#     'R2P': [
#         {'rule': rf'R2P PR, {r8}, {i20};', 'ptx': ptx_r2p}],
# }
