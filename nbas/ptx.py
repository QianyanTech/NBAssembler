#!/usr/bin/env python3
# coding: utf-8

# 先使用nvbit，把每一条指令的输入输出数据导出
# asm1 -> ptx : ptx中详细记录对应的ptx是由哪条指令转换而来
# ptx -> asm2 : 逐条将ptx分别构建cubin并测试，-O0

from .grammar import *


def ptx_i(captured_dict, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    i_str = captured_dict[name]
    if f'{name}neg' in captured_dict and captured_dict[f'{name}neg']:
        i_str = f'-{i_str}'
    return i_str


def ptx_r(captured_dict, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    r_str = f"%{captured_dict[name].lower()}"
    if 'rz' in r_str:
        r_str = '0'
        r_ord = -1
    else:
        r_ord = int(r_str.strip('%ur'), base=10)
    captured_dict[f'{name}ord'] = r_ord
    if f'{name}abs' in captured_dict and captured_dict[f'{name}abs']:
        r_str = f'|{r_str}|'
    if f'{name}neg' in captured_dict and captured_dict[f'{name}neg']:
        r_str = f'-{r_str}'
    return r_str


def ptx_p(captured_dict, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    p_str = f"%{captured_dict[name].lower()}"
    if 'pt' in p_str:
        p_ord = -1
        p_str = '1'
    else:
        p_ord = int(p_str.strip('%up'), base=10)
    captured_dict[f'{name}ord'] = p_ord
    if f'{name}not' in captured_dict and captured_dict[f'{name}not']:
        if p_ord != -1:
            p_str = f'!{p_str}'
        else:
            p_str = '0'
    return p_str


def ptx_new_reg(kernel):
    r_idx = kernel.reg_count + 256
    r_str = f'%r{r_idx}'
    kernel.reg_set.add(r_idx)
    kernel.reg_count += 1
    return r_str


def ptx_new_reg64(kernel):
    rd_idx = kernel.reg64_count
    kernel.reg64_count += 1
    return f'%rd{rd_idx}'


def ptx_cname(kernel, captured_dict, instr):
    name_str = captured_dict['name']
    offset = captured_dict['offset'] if captured_dict['offset'] else 0

    const0_map = {
        'BLOCK_DIM_X': '%ntid.x',
        'BLOCK_DIM_Y': '%ntid.y',
        'BLOCK_DIM_Z': '%ntid.z',
        'GRID_DIM_X': '%nctaid.x',
        'GRID_DIM_Y': '%nctaid.y',
        'GRID_DIM_Z': '%nctaid.z',
    }
    const0_dict = kernel.CONST0_VAL_61.copy() if kernel.arch < 70 else kernel.CONST0_VAL_75.copy()

    if name_str in const0_dict:
        if name_str not in const0_map:
            r_str = f'[{name_str}]'
        else:
            r_str = ptx_new_reg(kernel)
            instr.add_ptx('mov', f'.u32 {r_str}, {const0_map[name_str]};')
    elif 'mov' in instr.op.lower() or 'ld' in instr.op.lower():
        r_str = f'[{name_str}+{offset}]'
    else:
        r_str = ptx_new_reg(kernel)
        ss_str = 'param' if 'ARG_' in name_str else 'const'
        instr.add_ptx('ld', f'.{ss_str}.b32 {r_str}, [{name_str}+{offset}];')
    if f'cnameabs' in captured_dict and captured_dict[f'cnameabs']:
        r_str = f'|{r_str}|'
    if f'cnameneg' in captured_dict and captured_dict[f'cnameneg']:
        r_str = f'-{r_str}'
    return r_str


def ptx_ir(captured_dict, i_name, r_name):
    c = ''
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    return c


def ptx_irc(kernel, captured_dict, instr, i_name, r_name):
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    else:
        c = ptx_cname(kernel, captured_dict, instr)
    return c


def ptx_rc(kernel, captured_dict, instr, r_name):
    if r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    else:
        c = ptx_cname(kernel, captured_dict, instr)
    return c


def ptx_iurc(kernel, captured_dict, instr, i_name, r_name, ur_name):
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    elif ur_name in captured_dict and captured_dict[ur_name]:
        c = ptx_r(captured_dict, ur_name)
    else:
        c = ptx_cname(kernel, captured_dict, instr)
    return c


def ptx_r2d(kernel, captured_dict, instr, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    r_str = captured_dict[name]
    r_t = 'ur' if 'U' in r_str else 'r'
    if 'RZ' in r_str:
        return '0'
    r_idx = int(captured_dict[name].strip('UR'), base=0)
    rd_idx = kernel.reg64_count
    instr.add_ptx('mov', f'.b64 %rd{rd_idx}, {{%{r_t}{r_idx}, %{r_t}{r_idx + 1}}};')
    kernel.reg64_count += 1
    return f'%rd{rd_idx}'


def ptx_pack(kernel, instr, r1, r2):
    rd_idx = kernel.reg64_count
    instr.add_ptx('mov', f'.b64 %rd{rd_idx}, {{{r1}, {r2}}};')
    kernel.reg64_count += 1
    return f'%rd{rd_idx}'


def ptx_unpack(instr, r1, r2, rd1):
    instr.add_ptx('mov', f'.b64 {{{r1}, {r2}}}, {rd1};')


def ptx_append_instr(instrs, instr, op, rest):
    ptx = {
        'pred': instr['pred'],
        'op': op,
        'rest': rest,
    }
    instr.ptx.append(ptx)


def ptx_find_x(kernel, instr):
    line_num = instr['line_num']
    instr_x = None
    for n_instr in kernel.instrs[line_num + 1:]:
        rest = n_instr['rest']
        m = re.search(rf'\.X[. ]', rest)
        if m and n_instr['line_num'] and n_instr['line_num'] >= 0:
            instr_x = n_instr
            break
    return instr_x


def ptx_bfe(kernel, instrs, captured_dict, instr):
    type_str = 'u32' if captured_dict['U32'] else 's32'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    if '%r' in b:
        r_idx = kernel.reg_count + 256
        c = f'%r{r_idx}'
        kernel.reg_set.add(r_idx)
        kernel.ptx_reg_count += 1
        ptx_append_instr(instrs, instr, 'shr', f'.{type_str} {c}, {b}, 8;')
    else:
        b = int(b, base=0)
        c = b >> 8
        b = b & 0xff

    instr['op'] = 'bfe'
    instr['rest'] = f'.{type_str} {d}, {a}, {b}, {c};'


def ptx_bfi(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_ir(captured_dict, 'i20', 'r20')
    e = ptx_irc(kernel, instrs, captured_dict, instr, 'ixx', 'r39')
    if '%r' in b:
        r_idx = kernel.reg_count + 256
        c = f'%r{r_idx}'
        kernel.reg_set.add(r_idx)
        kernel.ptx_reg_count += 1
        ptx_append_instr(instrs, instr, 'shr', f'.b32 {c}, {b}, 8;')
    else:
        b = int(b, base=0)
        c = b >> 8
        b = b & 0xff

    instr['op'] = 'bfi'
    instr['rest'] = f'.b32 {d}, {a}, {e}, {b}, {c};'


def ptx_add(f, d, a, b):
    if '-' in a:
        op = 'sub'
        rest = f'{f}.s32 {d}, {b}, {a.strip("-")};'
    elif '-' in b:
        op = 'sub'
        rest = f'{f}.s32 {d}, {a}, {b.strip("-")};'
    else:
        op = 'add'
        rest = f'{f}.s32 {d}, {a}, {b};'
    return op, rest


def ptx_iadd(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')

    if '.CC' in instr['rest']:
        instr_x = ptx_find_x(kernel, instr)
        statement = instr_x['op'] + instr_x['rest']
        if m := re.search(rf'IADD\.X {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', statement):
            captured_dict_x = m.groupdict()
            instr_x['line_num'] = None
            d2 = ptx_r(captured_dict_x, 'r0')
            a2 = ptx_r(captured_dict_x, 'r8')
            b2 = ptx_irc(kernel, instrs, captured_dict_x, instr, 'i20', 'r20')
            da = ptx_pack(kernel, instrs, instr, a, a2)
            db = ptx_pack(kernel, instrs, instr, b, b2)
            rd_idx = kernel.reg64_count
            ptx_append_instr(instrs, instr, 'add', f'.s64 %rd{rd_idx}, {da}, {db};')
            kernel.reg64_count += 1
            dd = f'%rd{rd_idx}'
            ptx_unpack(instrs, instr, d, d2, dd)
            instr['line_num'] = None
        elif m := re.search(rf'ISETP{icmp}{u32}\.X\.AND {p3}, PT, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), PT;',
                            statement):
            captured_dict_x = m.groupdict()
            instr_x['line_num'] = None
            cmp_str = captured_dict_x['cmp'].lower()
            type_str = 'u64' if captured_dict_x['U32'] else 's64'
            d = ptx_p(captured_dict_x, 'p3')
            a2 = ptx_r(captured_dict_x, 'r8')
            b2 = ptx_irc(kernel, instrs, captured_dict_x, instr, 'i20', 'r20')
            da = ptx_pack(kernel, instrs, instr, a, a2)
            db = ptx_pack(kernel, instrs, instr, b.strip('-'), b2)
            instr['op'] = 'setp'
            instr['rest'] = f'.{cmp_str}.{type_str} {d}, {da}, {db};'
        else:
            instr['line_num'] = -instr['line_num']
    else:
        sat_str = captured_dict['SAT'].lower() if captured_dict['SAT'] else ''
        instr['op'], instr['rest'] = ptx_add(sat_str, d, a, b)


def ptx_iadd32i(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_i(captured_dict, 'i20')
    if '.CC' in instr['rest']:
        instr_x = ptx_find_x(kernel, instr)
        statement = instr_x['op'] + instr_x['rest']
        if (m := re.search(rf'IADD\.X {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', statement)) \
                or (m := re.search(rf'IADD32I\.X {r0}, {r8}, {i20};', statement)):
            captured_dict_x = m.groupdict()
            instr_x['line_num'] = None
            d2 = ptx_r(captured_dict_x, 'r0')
            a2 = ptx_r(captured_dict_x, 'r8')
            b2 = ptx_irc(kernel, instrs, captured_dict_x, instr, 'i20', 'r20')
            da = ptx_pack(kernel, instrs, instr, a, a2)
            db = ptx_pack(kernel, instrs, instr, b, b2)
            rd_idx = kernel.reg64_count
            ptx_append_instr(instrs, instr, 'add', f'.s64 %rd{rd_idx}, {da}, {db};')
            kernel.reg64_count += 1
            dd = f'%rd{rd_idx}'
            ptx_unpack(instrs, instr, d, d2, dd)
            instr['line_num'] = None
        else:
            instr['line_num'] = -instr['line_num']
    else:
        instr['op'], instr['rest'] = ptx_add('', d, a, b)


def ptx_iscadd(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_i(captured_dict, 'i39w5')
    c = 1 << int(c, base=0)
    if '.CC' in instr['rest']:
        instr_x = ptx_find_x(kernel, instr)
        statement = instr_x['op'] + instr_x['rest']
        if m := re.search(rf'IADD\.X {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', statement):
            captured_dict_x = m.groupdict()
            instr_x['line_num'] = None
            d2 = ptx_r(captured_dict_x, 'r0')
            b2 = ptx_irc(kernel, instrs, captured_dict_x, instr, 'i20', 'r20')
            db = ptx_pack(kernel, instrs, instr, b, b2)
            rd_idx = kernel.reg64_count
            ptx_append_instr(instrs, instr, 'mul', f'.wide.u32 %rd{rd_idx}, {a}, {c};')
            kernel.reg64_count += 1
            ptx_append_instr(instrs, instr, 'add', f'.s64 {db}, %rd{rd_idx}, {db};')
            ptx_unpack(instrs, instr, d, d2, db)
            instr['line_num'] = None
        else:
            instr['line_num'] = -instr['line_num']
    else:
        instr['op'] = 'mad'
        instr['rest'] = f'.lo.s32 {d}, {a}, {c}, {b};'


def ptx_lea(kernel, instrs, captured_dict, instr):
    instr['op'] = 'add'
    d = ptx_r(captured_dict, 'r0')
    a_lo = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    a_hi = ptx_r(captured_dict, 'r39')
    c = ptx_i(captured_dict, 'i28w5')

    r_idx = kernel.reg_count + 256
    r_str = f'%r{r_idx}'
    ptx_append_instr(instrs, instr, 'shf', f'.l.wrap.b32 {r_str}, {a_lo}, {a_hi}, {c};')
    kernel.reg_set.add(r_idx)
    kernel.ptx_reg_count += 1

    rest = f'.s32 {d}, {b}, {r_str};'
    instr['rest'] = rest


def ptx_xmad(kernel, instrs, captured_dict, instr):
    mode = captured_dict['mode']
    line_num = instr['line_num']
    a_full = captured_dict["a"]
    if '.H1' in a_full:
        a_full = a_full[:-3]
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    b_full = captured_dict["b"]
    b_full = b_full.replace('[', '\\[')
    b_full = b_full.replace(']', '\\]')
    b_full = b_full.replace('+', '\\+')
    if '.H1' in b_full:
        b_full = b_full[:-3]
    c1 = c3 = c = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r39')
    captured_dict1 = None
    captured_dict2 = None
    captured_dict3 = None
    captured_dict_chi = None
    captured_dict_mrg = None
    captured_dict_l = None

    if not mode:
        if '.H1' in captured_dict['a']:
            captured_dict3 = captured_dict
            c3 = c
        elif '.H1' in captured_dict['b']:
            captured_dict2 = captured_dict
        else:
            captured_dict1 = captured_dict
            c1 = c
    elif mode == 'MRG':
        captured_dict_mrg = captured_dict

    for n_instr in kernel.instrs[line_num + 1:]:
        statement = n_instr['op'] + n_instr['rest']
        if m := re.search(rf'XMAD (?P<d>{r0}), {a_full}, {b_full}, (?P<c>(?:{r39}|{i20}|{CONST_NAME_RE}));', statement):
            captured_dict1 = m.groupdict()
            n_instr['line_num'] = None
            c1 = ptx_irc(kernel, instrs, captured_dict1, instr, 'i20', 'r39')
        elif m := re.search(rf'XMAD\.MRG (?P<d>{r0}), {a_full}, {b_full}\.H1, RZ;', statement):
            captured_dict_mrg = m.groupdict()
            n_instr['line_num'] = None
        elif m := re.search(rf'XMAD\.CHI (?P<d>{r0}), {a_full}\.H1, {b_full},', statement):
            captured_dict_chi = m.groupdict()
            n_instr['line_num'] = None
        elif m := re.search(rf'XMAD (?P<d>{r0}), {a_full}, {b_full}\.H1, RZ;', statement):
            captured_dict2 = m.groupdict()
            n_instr['line_num'] = None
        elif m := re.search(rf'XMAD (?P<d>{r0}), {a_full}\.H1, {b_full}\.H1, (?P<c>(?:{r39}|{i20}|{CONST_NAME_RE}));',
                            statement):
            captured_dict3 = m.groupdict()
            n_instr['line_num'] = None
            c3 = ptx_irc(kernel, instrs, captured_dict3, instr, 'i20', 'r39')
        elif captured_dict1 and (
                m := re.search(rf'XMAD\.PSL {r0}, {a_full}\.H1, {b_full}, {captured_dict1["d"]};', statement)):
            captured_dict_l = m.groupdict()
            n_instr['line_num'] = None
            d = ptx_r(captured_dict_l, 'r0')
            instr['op'] = 'mad'
            instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
            break
        elif captured_dict_mrg and captured_dict1 and (m := re.search(
                rf'XMAD\.PSL\.CBCC {r0}, {a_full}\.H1, {captured_dict_mrg["d"]}\.H1, {captured_dict1["d"]};',
                statement)):
            captured_dict_l = m.groupdict()
            n_instr['line_num'] = None
            d = ptx_r(captured_dict_l, 'r0')
            instr['op'] = 'mad'
            instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
            break
        elif captured_dict_chi and captured_dict2 and captured_dict3 and (m := re.search(
                rf'IADD3\.RS (?P<d>{r0}), {captured_dict_chi["d"]}, {captured_dict2["d"]}, {captured_dict3["d"]};',
                statement)):
            captured_dict_l = m.groupdict()
            n_instr['line_num'] = None
            d = ptx_r(captured_dict_l, 'r0')
            instr['op'] = 'mad'
            instr['rest'] = f'.hi.u32 {d}, {a}, {b}, {c3};'
            break
    if not captured_dict_l:
        if captured_dict1:
            ptx_append_instr(instrs, instr, 'and', f'.b32 {a}, {a}, 0xffff;')
            if '%r' in b:
                ptx_append_instr(instrs, instr, 'and', f'.b32 {b}, {b}, 0xffff;')
            d = ptx_r(captured_dict1, 'r0')
            instr['op'] = 'mad'
            instr['rest'] = f'.lo.s32 {d}, {a}, {b}, {c1};'
        else:
            instr['line_num'] = -instr['line_num']


def ptx_icmp(kernel, instrs, captured_dict, instr):
    cmp_str = captured_dict['cmp'].lower()
    type_str = 'u32' if captured_dict['U32'] else 's32'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_r(captured_dict, 'r39')

    p_idx = kernel.ptx_pred_reg_count + 7
    kernel.pred_regs.add(p_idx)
    kernel.ptx_pred_reg_count += 1

    ptx_append_instr(instrs, instr, 'setp', f'.{cmp_str}.{type_str} %p{p_idx}, {c}, 0;')

    instr['op'] = 'selp'
    instr['rest'] = f'.b32 {d}, {a}, {b}, %p{p_idx};'


def ptx_lop(kernel, instrs, captured_dict, instr):
    instr['op'] = captured_dict['bool'].lower()
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    if captured_dict['INV8']:
        a = f'~{a}'
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    if instr['op'] == 'pass_b':
        instr['op'] = 'not'
        instr['rest'] = f'.b32 {d}, {b};'
    else:
        if captured_dict['TINV']:
            b = f'{~int(b, base=0)}'
        elif captured_dict['INV']:
            b = f'~{b}'
        instr['rest'] = f'.b32 {d}, {a}, {b};'


def ptx_psetp(kernel, instrs, captured_dict, instr):
    bool_str = captured_dict['bool'].lower()
    bool2_str = captured_dict['bool2'].lower()
    p = ptx_p(captured_dict, 'p3')
    q = ptx_p(captured_dict, 'p0')
    a = ptx_p(captured_dict, 'p12')
    b = ptx_p(captured_dict, 'p29')
    c = ptx_p(captured_dict, 'p39')
    a = a.replace('%pt', '1')
    b = b.replace('%pt', '1')
    c = c.replace('%pt', '1')
    ptx_append_instr(instrs, instr, bool_str, f'.pred {p}, {a}, {b};')
    if not ('1' == c and 'and' == bool_str):
        ptx_append_instr(instrs, instr, bool2_str, f'.pred {p}, {p}, {c};')
    if 'pt' not in q:
        ptx_append_instr(instrs, instr, 'not', f'.pred {q}, {p};')
    instr['line_num'] = None


def ptx_lop32i(kernel, instrs, captured_dict, instr):
    instr['op'] = captured_dict['bool2'].lower()
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    if captured_dict['INV8']:
        a = f'~{a}'
    b = ptx_i(captured_dict, 'i20w32')
    rest = f'.b32 {d}, {a}, {b};'
    instr['rest'] = rest


def ptx_shl(kernel, instrs, captured_dict, instr):
    instr['op'] = 'shl'
    type_str = '.b32'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    rest = f'{type_str} {d}, {a}, {b};'
    instr['rest'] = rest


def ptx_shr(kernel, instrs, captured_dict, instr):
    instr['op'] = 'shr'
    type_str = '.s32' if not captured_dict['U32'] else captured_dict['U32'].lower()
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    rest = f'{type_str} {d}, {a}, {b};'
    instr['rest'] = rest


def ptx_mov32i(kernel, instrs, captured_dict, instr):
    instr['op'] = 'mov'
    d = ptx_r(captured_dict, 'r0')
    if 'i20w32' in captured_dict:
        a = ptx_i(captured_dict, 'i20w32')
        instr['rest'] = f'.b32 {d}, {a};'
    else:
        type_str = captured_dict['type']
        line_num = instr['line_num']
        instr_hi = None
        for n_instr in kernel.instrs[line_num + 1:]:
            rest = n_instr['rest']
            m = re.search(rf'32@hi\({captured_dict["name"]}\)', rest)
            if m and n_instr['line_num'] >= 0:
                instr_hi = n_instr
                instr_hi['line_num'] = None
                break
        if 'lo' in type_str and instr_hi:
            rd_idx = kernel.reg64_count
            global_name = captured_dict['name']
            ptx_append_instr(instrs, instr, 'mov', f'.u64 %rd{rd_idx}, {global_name};')
            kernel.reg64_count += 1
            d_idx = captured_dict['r0ord']
            d = f'{{%r{d_idx}, %r{d_idx + 1}}}'
            instr['rest'] = f'.b64 {d}, %rd{rd_idx};'
        else:
            instr['line_num'] = -instr['line_num']


def ptx_sync(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bra'
    instr['rest'] = f' {captured_dict["label"]};'


def ptx_brk(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bra'
    instr['rest'] = f' {captured_dict["label"]};'


def ptx_bar(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bar'
    if captured_dict['i8w8']:
        i_str = ptx_i(captured_dict, 'i8w8')
        instr['rest'] = f'.sync {i_str};'
    else:
        instr['rest'] = instr['rest'].lower()
    pass


def ptx_r2p(kernel, instrs, captured_dict, instr):
    a = ptx_r(captured_dict, 'r8')
    b = ptx_i(captured_dict, 'i20')
    b = int(b, base=0) if b else 0
    for i in range(7):
        if b & (1 << i):
            kernel.pred_regs.add(i)
            r_idx = kernel.reg_count + 256
            r_str = f'%r{r_idx}'
            kernel.reg_set.add(r_idx)
            kernel.ptx_reg_count += 1
            ptx_append_instr(instrs, instr, 'and', f'.b32 {r_str}, {a}, {1 << i};')
            ptx_append_instr(instrs, instr, 'setp', f'.eq.s32 %p{i}, {r_str}, 0;')
    instr['line_num'] = None


ptx_ignore_instrs = ['NOP', 'MEMBAR', 'SSY', 'PBK']

pp = fr'(?P<pp>{P})'
pq = fr'(?P<pq>{P})'
pc = fr'(?P<pcnot>\!)?(?P<pc>{P})'
pcc1 = fr'(?P<pcc1>{P})'
pcc2 = fr'(?P<pcc2>{P})'
px1 = fr'(?P<px1not>\!)?(?P<px1>{P})'
px2 = fr'(?P<px2not>\!)?(?P<px2>{P})'
upcc1 = fr'(?P<upcc1>{UP})'
upcc2 = fr'(?P<upcc2>{UP})'
upx1 = fr'(?P<upx1not>\!)?(?P<px1>{UP})'
upx2 = fr'(?P<upx2not>\!)?(?P<px2>{UP})'
ra = fr'(?P<ra>{reg})'
rb = fr'(?P<rb>{reg})'
rc = fr'(?P<rcneg>[\-~])?(?P<rcabs>\|)?(?P<rc>{reg})\|?'
rd = fr'(?P<rd>{reg})'
urd = fr'(?P<urd>{ureg})'
ura = fr'(?P<uraneg>[\-~])?(?P<uraabs>\|)?(?P<ura>{ureg})\|?'
urb = fr'(?P<urb>{ureg})'
urc = fr'(?P<urc>{ureg})'
pim = fr'(?P<pim>(?P<neg>\-)?{immed})'
imlut = fr'(?P<imlut>{immed})'
imask = fr'(?P<imask>{immed})'
paddr = fr'\[(?:(?P<ra>{reg})(?P<rax>\.X(4|8|16))?(?P<ratype>\.64|\.U32)?)?' \
        rf'(?:\s*\+?\s*(?P<ura>{ureg}))?(?:\s*\+?\s*{pim})?\]'

cname = fr'(?P<cnameneg>\-)?(?P<cnameabs>\|)?{CONST_NAME_RE}\|?'
pldc = rf'c\[(?P<cbank>{hexx})\]\s*\[(?P<rb>{reg})?(?:\s*\+?\s*{pim})?\]'


def ptx_mov(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_irc(kernel, captured_dict, instr, 'pim', 'rc')
    # if captured_dict['const']:
    #     ss_str = 'param' if 'ARG_' in captured_dict['name'] else 'const'
    #     instr.add_ptx('ld', f'.{ss_str}.b32 {d}, {a};')
    # else:
    #     instr.add_ptx('mov', f'.b32 {d}, {a};')
    instr.add_ptx('mov', f'.b32 {d}, {a};')


def ptx_uldc(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'urd')
    d_idx = captured_dict['urdord']
    a = ptx_cname(kernel, captured_dict, instr)
    if captured_dict['type'] and '64' in captured_dict['type']:
        d = f'{{%ur{d_idx}, %ur{d_idx + 1}}}'
    elif captured_dict['type'] and '128' in captured_dict['type']:
        d = f'{{%ur{d_idx}, %ur{d_idx + 1}, %ur{d_idx + 2}, %ur{d_idx + 3}}}'
    ss_str = 'param' if 'ARG_' in captured_dict['name'] else 'const'
    type_str = '.u32'
    v_str = ''
    if captured_dict['type']:
        if '64' in captured_dict['type']:
            v_str = '.v2'
        elif '128' in captured_dict['type']:
            v_str = '.v4'
        elif '32' not in captured_dict['type']:
            type_str = captured_dict['type'].lower()
    instr.add_ptx('ld', f'.{ss_str}{v_str}{type_str} {d}, {a};')


def ptx_umov(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'urd')
    a = ptx_ir(captured_dict, 'pim', 'ura')
    if a:
        instr.add_ptx('mov', f'.b32 {d}, {a};')
    else:
        type_str = captured_dict['type']
        if '32@' in type_str:
            global_name = captured_dict['name']
            rd_idx = kernel.reg64_count
            instr.add_ptx('mov', f'.u64 %rd{rd_idx}, {global_name};')
            kernel.reg64_count += 1
            d_idx = captured_dict['urdord']
            if '32@lo' in type_str:
                d = f'{{%ur{d_idx}, %ur{d_idx + 1}}}'
            else:
                d = f'{{%ur{d_idx - 1}, %ur{d_idx}}}'
            instr.add_ptx('mov', f'.b64 {d}, %rd{rd_idx};')
        else:
            instr.ptx = []


def ptx_addr(kernel, captured_dict, instr):
    ss = instr.op[-1]
    if ss in ['L', 'S', 'C']:
        a = ptx_r(captured_dict, 'ra')
        b = ptx_r(captured_dict, 'ura')
    else:
        a = ptx_r2d(kernel, captured_dict, instr, 'ra')
        b = ptx_r2d(kernel, captured_dict, instr, 'ura')
    if a in ['0', '-0', '|0|', '']:
        if ss == 'S':
            a = '_shared+'
        else:
            a = ''
    else:
        a = f'{a}+'
    c = ptx_i(captured_dict, 'pim')
    c = int(c, base=0) if c else 0
    if c:
        b += f'+{c}'
    return f'[{a}{b}]'


def ptx_ldst(kernel, captured_dict, instr):
    op = instr.op
    if op in ['LDL', 'STL']:
        ss = 'local'
    elif op in ['LDS', 'STS']:
        ss = 'shared'
    elif op == 'LDC':
        ss = 'const'
    else:
        ss = 'global'

    if captured_dict['cache']:
        cache_str = f'.{captured_dict["cache"].lower()}'
    else:
        cache_str = ''
    if cache_str == '.ci':
        cache_str = '.nc'
    elif cache_str == '.wt':
        cache_str = '.volatile'

    if 'LD' in op:
        d = ptx_r(captured_dict, 'rd')
        d_idx = captured_dict['rdord']
    else:
        d = ptx_r(captured_dict, 'rc')
        d_idx = captured_dict['rcord']
    if captured_dict['type'] and '64' in captured_dict['type']:
        if d_idx == -1:
            d = f'{{0, 0}}'
        else:
            d = f'{{%r{d_idx}, %r{d_idx + 1}}}'
    elif captured_dict['type'] and '128' in captured_dict['type']:
        if d_idx == -1:
            d = f'{{0, 0, 0, 0}}'
        else:
            d = f'{{%r{d_idx}, %r{d_idx + 1}, %r{d_idx + 2}, %r{d_idx + 3}}}'

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
    instr.add_ptx(op, f'.{ss}{cache_str}{v_str}{type_str} {dabc};')


def ptx_isetp(kernel, captured_dict, instr):
    cmp_str = captured_dict['cmp'].lower()
    bool_str = captured_dict['bool'].lower()
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    p = ptx_p(captured_dict, 'pp')
    q = ptx_p(captured_dict, 'pq')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_p(captured_dict, 'pc')
    if 'p' not in q:
        q = ''
    else:
        q = f'|{q}'
    if not c or (c == '1' and '.and' == bool_str) or (c == '0' and '.or' == bool_str):
        rest = f'{cmp_str}{type_str} {p}{q}, {a}, {b};'
    else:
        rest = f'{cmp_str}{bool_str}{type_str} {p}{q}, {a}, {b}, {c};'
    instr.add_ptx('setp', rest)


def ptx_exit(kernel, captured_dict, instr):
    instr.add_ptx('ret', ';')


def ptx_bra(kernel, captured_dict, instr):
    uni = '.uni' if captured_dict['U'] else ''
    instr.add_ptx('bra', f'{uni} {captured_dict["label"]};')


def ptx_s2r(kernel, captured_dict, instr):
    r_str = ptx_r(captured_dict, 'rd')
    sr_str = captured_dict['sr']
    if 'SRZ' == sr_str:
        sr_str = '0'
    else:
        sr_str = f"%{sr_str[3:].lower()}"
    instr.add_ptx('mov', f'.b32 {r_str}, {sr_str};')


def ptx_lop3(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_r(captured_dict, 'rc')
    lut = ptx_i(captured_dict, 'imlut')
    instr.add_ptx('lop3', f'.b32 {d}, {a}, {b}, {c}, {lut};')


def ptx_shf(kernel, captured_dict, instr):
    lr = captured_dict['lr'].lower()
    mode = '.wrap' if captured_dict['W'] else '.clamp'
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_r(captured_dict, 'rc')
    instr.add_ptx('shf', f'{lr}{mode}.b32 {d}, {a}, {c}, {b};')


def ptx_iadd3(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_r(captured_dict, 'rc')
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
            x1_ord = captured_dict['px1ord']
            x1_64 = ptx_pack(kernel, instr, f'%cc{x1_ord}', 0)
            instr.add_ptx('add', f'{type1} {ab64}, {ab64}, {x1_64};')
        ab = ptx_new_reg(kernel)
        cc1_ord = captured_dict['pcc1ord']
        kernel.pred_regs.add(cc1_ord)
        ptx_unpack(instr, ab, f'%cc{cc1_ord}', ab64)
    else:
        type1 = '.s32'
        ab = ptx_new_reg(kernel)
        instr.add_ptx('add', f'{type1} {ab}, {a}, {b};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['px1ord']
            instr.add_ptx('add', f'{type1} {ab}, {ab}, %cc{x1_ord};')

    if cc2 and cc2 != '0':
        type2 = '.s64'
        c64 = ptx_pack(kernel, instr, c, 0)
        ab64 = ptx_pack(kernel, instr, ab, 0)
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('add', f'{type2} {d64}, {ab64}, {c64};')
        if x2 and x2 != '0':
            x2_ord = captured_dict['px2ord']
            x2_64 = ptx_pack(kernel, instr, f'%cc{x2_ord}', 0)
            instr.add_ptx('add', f'{type1} {d64}, {d64}, {x2_64};')
        cc2_ord = captured_dict['pcc2ord']
        kernel.pred_regs.add(cc2_ord)
        ptx_unpack(instr, d, f'%cc{cc2_ord}', d64)
    else:
        type2 = '.s32'
        instr.add_ptx('add', f'{type2} {d}, {ab}, {c};')
        if x2 and x2 != '0':
            x2_ord = captured_dict['px2ord']
            instr.add_ptx('add', f'{type1} {d}, {d}, %cc{x2_ord};')


def ptx_uiadd3(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'urd')
    a = ptx_r(captured_dict, 'ura')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_r(captured_dict, 'urc')
    cc1 = ptx_p(captured_dict, 'upcc1')
    cc2 = ptx_p(captured_dict, 'upcc2')
    x1 = ptx_p(captured_dict, 'upx1')
    x2 = ptx_p(captured_dict, 'upx2')

    if cc1 and cc1 != '0':
        type1 = '.s64'
        a64 = ptx_pack(kernel, instr, a, 0)
        b64 = ptx_pack(kernel, instr, b, 0)
        ab64 = ptx_new_reg64(kernel)
        instr.add_ptx('add', f'{type1} {ab64}, {a64}, {b64};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['upx1ord']
            x1_64 = ptx_pack(kernel, instr, f'%ucc{x1_ord}', 0)
            instr.add_ptx('add', f'{type1} {ab64}, {ab64}, {x1_64};')
        ab = ptx_new_reg(kernel)
        cc1_ord = captured_dict['upcc1ord']
        kernel.pred_regs.add(cc1_ord)
        ptx_unpack(instr, ab, f'%ucc{cc1_ord}', ab64)
    else:
        type1 = '.s32'
        ab = ptx_new_reg(kernel)
        instr.add_ptx('add', f'{type1} {ab}, {a}, {b};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['upx1ord']
            instr.add_ptx('add', f'{type1} {ab}, {ab}, %ucc{x1_ord};')

    if cc2 and cc2 != '0':
        type2 = '.s64'
        c64 = ptx_pack(kernel, instr, c, 0)
        ab64 = ptx_pack(kernel, instr, ab, 0)
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('add', f'{type2} {d64}, {ab64}, {c64};')
        if x2 and x2 != '0':
            x2_ord = captured_dict['upx2ord']
            x2_64 = ptx_pack(kernel, instr, f'%ucc{x2_ord}', 0)
            instr.add_ptx('add', f'{type1} {d64}, {d64}, {x2_64};')
        cc2_ord = captured_dict['upcc2ord']
        kernel.pred_regs.add(cc2_ord)
        ptx_unpack(instr, d, f'%ucc{cc2_ord}', d64)
    else:
        type2 = '.s32'
        instr.add_ptx('add', f'{type2} {d}, {ab}, {c};')
        if x2 and x2 != '0':
            x2_ord = captured_dict['upx2ord']
            instr.add_ptx('add', f'{type1} {d}, {d}, %ucc{x2_ord};')


def ptx_imad(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_r(captured_dict, 'rc')
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
    #         x1_64 = ptx_pack(kernel, instr, f'%cc{x1_ord}', 0)
    #         instr.add_ptx('add', f'{type1} {ab64}, {ab64}, {x1_64};')
    #     ab = ptx_new_reg(kernel)
    #     cc1_ord = captured_dict['pcc1ord']
    #     kernel.pred_regs.add(cc1_ord)
    #     ptx_unpack(instr, ab, f'%cc{cc1_ord}', ab64)
    # else:
    if '.lo' == flag:
        instr.add_ptx('mad', f'.lo{type_str} {d}, {a}, {b}, {c};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['px1ord']
            instr.add_ptx('add', f'{type_str} {d}, {d}, %cc{x1_ord};')
    else:
        c64 = ptx_r2d(kernel, captured_dict, instr, c) if 'r' in c else c
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('mad', f'.wide{type_str} {d64}, {a}, {b}, {c64};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['px1ord']
            x1_64 = ptx_pack(kernel, instr, f'%cc{x1_ord}', 0)
            instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {x1_64};')
        d_ord = captured_dict['rdord']
        if '.wide' == flag:
            ptx_unpack(instr, d, f'%r{d_ord + 1}', d64)
        else:
            ptx_unpack(instr, ptx_new_reg(kernel), d, d64)


def ptx_imad2(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_r(captured_dict, 'rb')
    c = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rc', 'urc')
    x1 = ptx_p(captured_dict, 'px1')
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    flag = '.lo'
    if captured_dict['type'] and captured_dict['type'] in ['.WIDE', '.HI']:
        flag = captured_dict['type'].lower()

    if '.lo' == flag:
        instr.add_ptx('mad', f'.lo{type_str} {d}, {a}, {b}, {c};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['px1ord']
            instr.add_ptx('add', f'{type_str} {d}, {d}, %cc{x1_ord};')
    else:
        c64 = ptx_r2d(kernel, captured_dict, instr, c) if 'r' in c else c
        d64 = ptx_new_reg64(kernel)
        instr.add_ptx('mad', f'.wide{type_str} {d64}, {a}, {b}, {c64};')
        if x1 and x1 != '0':
            x1_ord = captured_dict['px1ord']
            x1_64 = ptx_pack(kernel, instr, f'%cc{x1_ord}', 0)
            instr.add_ptx('add', f'{type_str.replace("32", "64")} {d64}, {d64}, {x1_64};')
        d_ord = captured_dict['rdord']
        if '.wide' == flag:
            ptx_unpack(instr, d, f'%r{d_ord + 1}', d64)
        else:
            ptx_unpack(instr, ptx_new_reg(kernel), d, d64)


def ptx_shfl(kernel, captured_dict, instr):
    p = ptx_p(captured_dict, 'pp')
    if 'p' not in p:
        p = ''
    else:
        p = f'|{p}'
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_ir(captured_dict, 'pim', 'rb')
    c = ptx_ir(captured_dict, 'imask', 'rc')
    mode = captured_dict["mode"].lower()
    instr.add_ptx('shfl', f'.sync.{mode}.b32 {d}{p}, {a}, {b}, {c}, -1;')


def ptx_sel(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_irc(kernel, captured_dict, instr, 'pim', 'rb')
    c = ptx_p(captured_dict, 'pc')
    instr.add_ptx('selp', f'.b32 {d}, {a}, {b}, {c};')


def ptx_imnmx(kernel, captured_dict, instr):
    type_str = '.u32' if captured_dict['U32'] else '.s32'
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_iurc(kernel, captured_dict, instr, 'pim', 'rb', 'urb')
    c = ptx_p(captured_dict, 'pc')
    if '!' in c or '0' == c:
        instr.add_ptx('max', f'{type_str} {d}, {a}, {b};')
    else:
        instr.add_ptx('min', f'{type_str} {d}, {a}, {b};')


def ptx_prmt(kernel, captured_dict, instr):
    d = ptx_r(captured_dict, 'rd')
    a = ptx_r(captured_dict, 'ra')
    b = ptx_ir(captured_dict, 'pim', 'rb')
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

    if '64' in type_str:
        b = ptx_r2d(kernel, captured_dict, instr, 'rb')
        c = ptx_r2d(kernel, captured_dict, instr, 'rc')
    else:
        b = ptx_r(captured_dict, 'rb')
        c = ptx_r(captured_dict, 'rc')

    if c:
        c = f', {c}'
    else:
        c = ''

    adr = ptx_addr(kernel, captured_dict, instr)

    d = ptx_r(captured_dict, 'rd')

    if '64' in type_str:
        d = ptx_r2d(kernel, captured_dict, instr, d)

    if d in ['', '0']:
        instr.add_ptx('red', f'{ss}{op_str}{type_str} {adr}, {b};')
    else:
        instr.add_ptx('atom', f'{ss}{op_str}{type_str} {d}, {adr}, {b}{c};')

    if '64' in type_str and d:
        d_idx = captured_dict['rdord']
        ptx_unpack(instr, f'%r{d_idx}', f'%r{d_idx + 1}', d)


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
    ],
    'FSET': [],  # FP32 Compare And Set
    'FSETP': [],  # FP32 Compare And Set Predicate
    'FSWZADD': [],  # FP32 Swizzle Add
    'MUFU': [  # FP32 Multi Function Operation
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
    ],
    'IABS': [  # Integer Absolute Value
    ],
    'IADD': [],  # Integer Addition
    'IADD3': [  # 3-input Integer Addition
        {'rule': rf'IADD3{X} {rd}, ({pcc1}, )?({pcc2}, )?{ra}, (?:{rb}|{urb}|{pim}|{cname}),'
                 rf' {rc}(, {px1})?(, {px2})?;', 'ptx': ptx_iadd3}
    ],
    'IADD32I': [],  # Integer Addition
    'IDP': [],  # Integer Dot Product and Accumulate
    'IDP4A': [],  # Integer Dot Product and Accumulate
    'IMAD': [  # Integer Multiply And Add
        {'rule': rf'IMAD\.MOV{u32} {rd}, RZ, RZ, (?:{pim}|{rc}|{CONST_NAME_RE});', 'ptx': ptx_mov},
        {'rule': rf'IMAD{timad}{u32}{X} {rd}, {ra}, (?:{rb}|{urb}|{pim}|{CONST_NAME_RE}), {rc}(, {px1})?;',
         'ptx': ptx_imad},
        {'rule': rf'IMAD{timad}{u32}{X} {rd}, {ra}, {rb}, (?:{rc}|{urc}|{pim}|{CONST_NAME_RE})(, {px1})?;',
         'ptx': ptx_imad2},
    ],
    'IMMA': [  # Integer Matrix Multiply and Accumulate
    ],
    'IMNMX': [  # Integer Minimum/Maximum
        {'rule': rf'IMNMX{u32} {rd}, {ra}, (?:{rb}|{urb}|{pim}|{cname}), {pc};', 'ptx': ptx_imnmx}
    ],
    'IMUL': [],  # Integer Multiply
    'IMUL32I': [],  # Integer Multiply
    'ISCADD': [],  # Scaled Integer Addition
    'ISCADD32I': [],  # Scaled Integer Addition
    'ISETP': [  # Integer Compare And Set Predicate
        {'rule': rf'ISETP{ticmp}{u32}{tbool} {pp}, {pq}, {ra},'
                 rf' (?:{rb}|{urb}|{pim}|{CONST_NAME_RE}), {pc}(, {px1})?;',
         'ptx': ptx_isetp}
    ],
    'LEA': [  # LOAD Effective Address
    ],
    'LOP': [],  # Logic Operation
    'LOP3': [  # Logic Operation
        {'rule': rf'LOP3\.LUT{tpand} ({pp}, )?{rd}, {ra}, (?:{rb}|{urb}|{pim}|{CONST_NAME_RE}), {rc}, {imlut}, {pc};',
         'ptx': ptx_lop3},
    ],
    'LOP32I': [],  # Logic Operation
    'POPC': [  # Population count
    ],
    'SHF': [  # Funnel Shift
        {'rule': rf'SHF{tshf_lr}{tw}{tshf_type} {rd}, {ra}, (?:{rb}|{urb}|{pim}|{CONST_NAME_RE}), {rc};',
         'ptx': ptx_shf},
    ],
    'SHL': [],  # Shift Left
    'SHR': [],  # Shift Right
    'VABSDIFF': [],  # Absolute Difference
    'VABSDIFF4': [],  # Absolute Difference

    # Conversion Instructions
    'F2F': [],  # Floating Point To Floating Point Conversion
    'F2I': [  # Floating Point To Integer Conversion
    ],
    'I2F': [  # Integer To Floating Point Conversion
    ],
    'I2I': [],  # Integer To Integer Conversion
    'I2IP': [],  # Integer To Integer Conversion and Packing
    'FRND': [],  # Round To Integer

    # Movement Instructions
    'MOV': [  # Move
    ],
    'MOV32I': [],  # Move
    'MOVM': [],  # Move Matrix with Transposition or Expansion
    'PRMT': [  # Permute Register Pair
        {'rule': rf'PRMT{tprmt} {rd}, {ra}, (?:{rb}|{pim}), (?:{rc}|{cname});', 'ptx': ptx_prmt}
    ],
    'SEL': [  # Select Source with Predicate
        {'rule': rf'SEL {rd}, {ra}, (?:{rb}|{pim}|{CONST_NAME_RE}), {pc};', 'ptx': ptx_sel}
    ],
    'SGXT': [  # Sign Extend
    ],
    'SHFL': [  # Warp Wide Register Shuffle
        {'rule': rf'SHFL{shfl} {pp}, {rd}, {ra}, (?:{pim}|{rb}), (?:{imask}|{rc});', 'ptx': ptx_shfl}
    ],

    # Predicate Instructions
    'PLOP3': [  # Predicate Logic Operation
    ],
    'PSETP': [],  # Combine Predicates and Set Predicate
    'P2R': [  # Move Predicate Register To Register
    ],
    'R2P': [],  # Move Register To Predicate Register

    # Load/Store Instructions
    'LD': [  # Load from generic Memory
    ],
    'LDC': [  # Load Constant
        {'rule': rf'LDC{tmem_type}{tldc_isl} {rd}, {cname};', 'ptx': ptx_ldst},
    ],
    'LDG': [  # Load from Global Memory
        {'rule': rf'LDG{te}{tmem_cache}{tmem_ltc}{tmem_type}{tmem_scopes}{tzd} {rd}, {paddr};', 'ptx': ptx_ldst}
    ],
    'LDGDEPBAR': [],  # Global Load Dependency Barrier
    'LDGSTS': [],  # Asynchronous Global to Shared Memcopy
    'LDL': [  # Load within Local Memory Window
    ],
    'LDS': [  # Load within Shared Memory Window
    ],
    'LDSM': [],  # Load Matrix from Shared Memory with Element Size Expansion
    'ST': [
    ],  # Store to Generic Memory
    'STG': [  # Store to Global Memory
        {'rule': rf'STG{te}{tmem_cache}{tmem_type}{tmem_scopes}{tzd} {paddr}, {rc};', 'ptx': ptx_ldst}
    ],
    'STL': [  # Store within Local or Shared Window
    ],
    'STS': [  # Store within Local or Shared Window
    ],
    'MATCH': [],  # Match Register Values Across Thread Group
    'QSPC': [],  # Query Space
    'ATOM': [
    ],  # Atomic Operation on Generic Memory
    'ATOMS': [  # Atomic Operation on Shared Memory
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
    ],
    'UBMSK': [],  # Uniform Bitfield Mask
    'UBREV': [],  # Uniform Bit Reverse
    'UCLEA': [],  # Load Effective Address for a Constant
    'UFLO': [  # Uniform Find Leading One
    ],
    'UIADD3': [  # Uniform Integer Addition
        {'rule': rf'IADD3{X} {urd}, ({upcc1}, )?({upcc2}, )?{ura}, (?:{urb}|{pim}|{cname}),'
                 rf' {urc}(, {upx1})?(, {upx2})?;', 'ptx': ptx_uiadd3}
    ],
    'UIMAD': [  # Uniform Integer Multiplication
    ],
    'UISETP': [  # Integer Compare and Set Uniform Predicate
    ],
    'ULDC': [  # Load from Constant Memory into a Uniform Register
        {'rule': rf'ULDC{tmem_type} {urd}, {cname};', 'ptx': ptx_uldc}
    ],
    'ULEA': [  # Uniform Load Effective Address
    ],
    'ULOP': [],  # Logic Operation
    'ULOP3': [  # Logic Operation
    ],
    'ULOP32I': [],  # Logic Operation
    'UMOV': [  # Uniform Move
        {'rule': rf'UMOV {urd}, (?:{pim}|{ura}|{GLOBAL_NAME_RE});', 'ptx': ptx_umov},
    ],
    'UP2UR': [],  # Uniform Predicate to Uniform Register
    'UPLOP3': [],  # Uniform Predicate Logic Operation
    'UPOPC': [  # Uniform Population Count
    ],
    'UPRMT': [  # Uniform Byte Permute
    ],
    'UPSETP': [],  # Uniform Predicate Logic Operation
    'UR2UP': [],  # Uniform Register to Uniform Predicate
    'USEL': [  # Uniform Select
    ],
    'USGXT': [],  # Uniform Sign Extend
    'USHF': [  # Uniform Funnel Shift
    ],
    'USHL': [],  # Uniform Left Shift
    'USHR': [],  # Uniform Right Shift
    'VOTEU': [  # Voting across SIMD Thread Group with Results in Uniform Destination
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
    ],

}

grammar_ptx_old = {
    # Integer Instructions
    'BFE': [
        {'rule': rf'BFE{u32} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_bfe}],
    'BFI': [
        {'rule': rf'BFI {r0nc}, {r8}, (?:{r20}|{i20}), (?:{r39}|{CONST_NAME_RE});', 'ptx': ptx_bfi}],
    'IMNMX': [  # max min
        {'rule': rf'IMNMX{u32} {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {p39};', 'ptx': ptx_imnmx}],
    'IADD': [  # add
        {'rule': rf'IADD{sat} {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_iadd}],
    'IADD32I': [  # add
        {'rule': rf'IADD32I {r0}, {r8}, {i20};', 'ptx': ptx_iadd32i}],
    'ISCADD': [  # add
        {'rule': rf'ISCADD {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {i39w5};', 'ptx': ptx_iscadd}],
    'LEA': [  # shf.l + add
        {'rule': rf'LEA {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {i39w5};', 'ptx': ptx_iscadd},
        {'rule': rf'LEA\.HI {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39}, {i28w5};', 'ptx': ptx_lea}],
    'XMAD': [  # mad
        {'rule': rf'XMAD{xmad} (?P<d>{r0nc}), (?P<a>{r8}), (?P<b>(?:{r20}|{i20}|{CONST_NAME_RE})), (?P<c>{r39});',
         'ptx': ptx_xmad},
        {'rule': rf'XMAD{xmad} (?P<d>{r0nc}), (?P<a>{r8}), (?P<b>{r20}), (?P<c>(?:{i20}|{CONST_NAME_RE}));',
         'ptx': ptx_xmad}],

    # Comparison and Selection Instructions
    'ICMP': [  # slct
        {'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_icmp}],
    # Logic and Shift Instructions
    'LOP': [  # and or xor not
        {'rule': rf'LOP{bool_} {r0nc}, (?P<INV8>~)?{r8}, (?P<INV>~)?(?:{r20}|{i20}|{CONST_NAME_RE})(?P<TINV>\.INV)?;',
         'ptx': ptx_lop}],
    'LOP32I': [  # and or xor not
        {'rule': rf'LOP32I{bool2} {r0nc}, (?P<INV8>~)?{r8}, {i20w32};', 'ptx': ptx_lop32i}],
    'SHL': [  # shl
        {'rule': rf'SHL {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_shl}],
    'SHR': [  # shr
        {'rule': rf'SHR{u32} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_shr}],
    # Movement Instructions
    'MOV32I': [  # mov
        {'rule': rf'MOV32I {r0nc}, {i20w32};', 'ptx': ptx_mov32i},
        {'rule': rf'MOV32I {r0nc}, {GLOBAL_NAME_RE};', 'ptx': ptx_mov32i}],
    'PRMT': [  # prmt
        {'rule': rf'PRMT{prmt} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_prmt}],
    'SEL': [  # selp
        {'rule': rf'SEL {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {p39};', 'ptx': ptx_sel}],
    # Predicate/CC Instructions
    'PSETP': [  # setp
        {'rule': rf'PSETP(?:\.(?P<bool>AND|OR|XOR)){bool2} {p3}, {p0}, {p12}, {p29}, {p39};', 'ptx': ptx_psetp}],
    # Compute Load/Store Instructions
    'STG': [  # st
        {'rule': rf'STG{mem_cache}{mem_type} {addr}, {r0nc};', 'ptx': ptx_ldst}],
    'LDS': [  # ld
        {'rule': rf'LDS{mem_cache}{mem_type} {r0nc}, {addr};', 'ptx': ptx_ldst}],
    'STS': [  # st
        {'rule': rf'STS{mem_cache}{mem_type} {addr}, {r0nc};', 'ptx': ptx_ldst}],
    'LDL': [  # ld
        {'rule': rf'LDL{mem_cache}{mem_type} {r0nc}, {addr};', 'ptx': ptx_ldst}],
    'STL': [  # st
        {'rule': rf'STL{mem_cache}{mem_type} {addr}, {r0nc};', 'ptx': ptx_ldst}],
    'LDC': [  # ld
        {'rule': rf'LDC{mem_cache}{mem_type} {r0nc}, {ldc};', 'ptx': ptx_ldst}],
    'BRK': [  # bra
        {'rule': rf'BRK `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_brk}],
    'SYNC': [  # bra
        {'rule': rf'SYNC `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_sync}],

    # Miscellaneous Instructions
    'BAR': [  # bar
        {'rule': rf'BAR\.SYNC (?:{i8w8}|{r8});', 'ptx': ptx_bar}],
    'R2P': [
        {'rule': rf'R2P PR, {r8}, {i20};', 'ptx': ptx_r2p}],
}
