#!/usr/bin/env python3
# coding: utf-8

# 先使用nvbit，把每一条指令的输入输出数据导出
# asm1 -> ptx : ptx中详细记录对应的ptx是由哪条指令转换而来
# ptx -> asm2 : 逐条将ptx分别构建cubin并测试，-O0

from .grammar import *


def ptx_i(captured_dict, name):
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
        r_ord = int(r_str[2:], base=10)
    captured_dict[f'{name}ord'] = r_ord
    if f'{name}abs' in captured_dict and captured_dict[f'{name}abs']:
        r_str = f'|{r_str}|'
    if f'{name}neg' in captured_dict and captured_dict[f'{name}neg']:
        r_str = f'-{r_str}'
    return r_str


def ptx_p(captured_dict, name):
    p_str = f"%{captured_dict[name].lower()}"
    if 'pt' in p_str:
        p_ord = -1
    else:
        p_ord = int(p_str[2:], base=10)
    captured_dict[f'{name}ord'] = p_ord
    if f'{name}not' in captured_dict and captured_dict[f'{name}not']:
        p_str = f'!{p_str}'
    return p_str


def ptx_cname(kernel, instrs, captured_dict, instr):
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

    if name_str in kernel.CONST0_VAL:
        if name_str not in const0_map:
            r_str = f'[{name_str}]'
        else:
            r_idx = kernel.ptx_reg_count + 256
            r_str = f'%r{r_idx}'
            instrs.append({
                'line_num': instr['line_num'],
                'ctrl': instr['ctrl'],
                'pred': instr['pred'],
                'pred_not': instr['pred_not'],
                'op': 'mov',
                'rest': f'.u32 {r_str}, {const0_map[name_str]};',
                'label': instr['label'],
            })
            instr['label'] = ''
            kernel.reg_set.add(r_idx)
            kernel.ptx_reg_count += 1
    elif 'mov' in instr['op'].lower() or 'ld' in instr['op'].lower():
        r_str = f'[{name_str}+{offset}]'
    else:
        r_idx = kernel.ptx_reg_count + 256
        r_str = f'%r{r_idx}'
        ss_str = 'param' if 'PARAM' in name_str else 'const'
        instrs.append({
            'line_num': instr['line_num'],
            'ctrl': instr['ctrl'],
            'pred': instr['pred'],
            'pred_not': instr['pred_not'],
            'op': 'ld',
            'rest': f'.{ss_str}.b32 {r_str}, [{name_str}+{offset}];',
            'label': instr['label'],
        })
        instr['label'] = ''
        kernel.reg_set.add(r_idx)
        kernel.ptx_reg_count += 1
    if f'c20abs' in captured_dict and captured_dict[f'c20abs']:
        r_str = f'|{r_str}|'
    if f'c20neg' in captured_dict and captured_dict[f'c20neg']:
        r_str = f'-{r_str}'
    return r_str


def ptx_ir(captured_dict, i_name, r_name):
    c = ''
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    return c


def ptx_irc(kernel, instrs, captured_dict, instr, i_name, r_name):
    if i_name in captured_dict and captured_dict[i_name]:
        c = ptx_i(captured_dict, i_name)
    elif r_name in captured_dict and captured_dict[r_name]:
        c = ptx_r(captured_dict, r_name)
    else:
        c = ptx_cname(kernel, instrs, captured_dict, instr)
    return c


def ptx_r2d(kernel, instrs, captured_dict, instr, name):
    if name not in captured_dict or not captured_dict[name]:
        return ''
    if 'RZ' in captured_dict[name]:
        return '0'
    r_idx = int(captured_dict[name][1:], base=0)
    rd_idx = kernel.reg64_count
    instrs.append({
        'line_num': instr['line_num'],
        'ctrl': instr['ctrl'],
        'pred': instr['pred'],
        'pred_not': instr['pred_not'],
        'op': 'mov',
        'rest': f'.b64 %rd{rd_idx}, {{%r{r_idx}, %r{r_idx + 1}}};',
        'label': instr['label'],
    })
    instr['label'] = ''
    kernel.reg64_count += 1
    return f'%rd{rd_idx}'


def ptx_pack(kernel, instrs, instr, r1, r2):
    rd_idx = kernel.reg64_count
    instrs.append({
        'line_num': instr['line_num'],
        'ctrl': instr['ctrl'],
        'pred': instr['pred'],
        'pred_not': instr['pred_not'],
        'op': 'mov',
        'rest': f'.b64 %rd{rd_idx}, {{{r1}, {r2}}};',
        'label': instr['label'],
    })
    instr['label'] = ''
    kernel.reg64_count += 1
    return f'%rd{rd_idx}'


def ptx_unpack(instrs, instr, r1, r2, rd):
    instrs.append({
        'line_num': instr['line_num'],
        'ctrl': instr['ctrl'],
        'pred': instr['pred'],
        'pred_not': instr['pred_not'],
        'op': 'mov',
        'rest': f'.b64 {{{r1}, {r2}}}, {rd};',
        'label': instr['label'],
    })
    instr['label'] = ''


def ptx_append_instr(instrs, instr, op, rest):
    instrs.append({
        'line_num': instr['line_num'],
        'ctrl': instr['ctrl'],
        'pred': instr['pred'],
        'pred_not': instr['pred_not'],
        'op': op,
        'rest': rest,
        'label': instr['label'],
    })
    instr['label'] = ''


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
        r_idx = kernel.ptx_reg_count + 256
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
        r_idx = kernel.ptx_reg_count + 256
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


def ptx_imnmx(kernel, instrs, captured_dict, instr):
    type_str = 'u32' if captured_dict['U32'] else 's32'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_p(captured_dict, 'p39')
    if '!' in c:
        instr['op'] = 'max'
    else:
        instr['op'] = 'min'
    instr['rest'] = f'.{type_str} {d}, {a}, {b};'


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


def ptx_iadd3(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_r(captured_dict, 'r39')
    if '.CC' in instr['rest']:
        instr_x = ptx_find_x(kernel, instr)
        statement = instr_x['op'] + instr_x['rest']
        if m := re.search(rf'IADD3\.X {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', statement):
            captured_dict_x = m.groupdict()
            instr_x['line_num'] = None
            d2 = ptx_r(captured_dict_x, 'r0')
            a2 = ptx_r(captured_dict_x, 'r8')
            b2 = ptx_irc(kernel, instrs, captured_dict_x, instr, 'i20', 'r20')
            c2 = ptx_r(captured_dict_x, 'r39')
            da = ptx_pack(kernel, instrs, instr, a, a2)
            db = ptx_pack(kernel, instrs, instr, b, b2)
            dc = ptx_pack(kernel, instrs, instr, c, c2)
            rd_idx = kernel.reg64_count
            ptx_append_instr(instrs, instr, 'add', f'.s64 %rd{rd_idx}, {da}, {db};')
            ptx_append_instr(instrs, instr, 'add', f'.s64 %rd{rd_idx}, %rd{rd_idx}, {dc};')
            kernel.reg64_count += 1
            dd = f'%rd{rd_idx}'
            ptx_unpack(instrs, instr, d, d2, dd)
            instr['line_num'] = None
        else:
            instr['line_num'] = -instr['line_num']
    else:
        ptx_append_instr(instrs, instr, *ptx_add('', d, a, b))
        instr['op'], instr['rest'] = ptx_add('', d, d, c)


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

    r_idx = kernel.ptx_reg_count + 256
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


def ptx_isetp(kernel, instrs, captured_dict, instr):
    instr['op'] = 'setp'
    cmp_str = captured_dict['cmp'].lower()
    bool_str = captured_dict['bool2'].lower()
    type_str = 'u32' if captured_dict['U32'] else 's32'
    p = ptx_p(captured_dict, 'p3')
    q = ptx_p(captured_dict, 'p0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_p(captured_dict, 'p39')
    if 'pt' in q:
        q = ''
    else:
        q = f'|{q}'
    if '%pt' == c and 'and' == bool_str:
        rest = f'.{cmp_str}.{type_str} {p}{q}, {a}, {b};'
    else:
        rest = f'.{cmp_str}.{bool_str}.{type_str} {p}{q}, {a}, {b}, {c};'
    instr['rest'] = rest


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


def ptx_lop3(kernel, instrs, captured_dict, instr):
    instr['op'] = 'lop3'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_r(captured_dict, 'r39')
    lut = ptx_i(captured_dict, 'i28w8')
    rest = f'.b32 {d}, {a}, {b}, {c}, {lut};'
    instr['rest'] = rest


def ptx_shf(kernel, instrs, captured_dict, instr):
    instr['op'] = 'shf'
    lr = captured_dict['lr'].lower()
    mode = 'wrap' if captured_dict['W'] else 'clamp'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_ir(captured_dict, 'i20', 'r20')
    c = ptx_r(captured_dict, 'r39')
    rest = f'.{lr}.{mode}.b32 {d}, {a}, {c}, {b};'
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


def ptx_mov(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    if captured_dict['const']:
        instr['op'] = 'ld'
        ss_str = 'param' if 'PARAM' in captured_dict['name'] else 'const'
        instr['rest'] = f'.{ss_str}.b32 {d}, {a};'
    else:
        instr['op'] = 'mov'
        instr['rest'] = f'.b32 {d}, {a};'


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


def ptx_shfl(kernel, instrs, captured_dict, instr):
    instr['op'] = 'shfl'
    p = ptx_p(captured_dict, 'p48')
    if 'pt' in p:
        p = ''
    else:
        p = f'|{p}'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_ir(captured_dict, 'i20w8', 'r20')
    c = ptx_ir(captured_dict, 'i34w13', 'r39')
    mode = captured_dict["mode"].lower()
    instr['rest'] = f'.sync.{mode}.b32 {d}{p}, {a}, {b}, {c}, -1;'


def ptx_prmt(kernel, instrs, captured_dict, instr):
    instr['op'] = 'prmt'
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_r(captured_dict, 'r39')
    mode = '' if not captured_dict['mode'] else f'.{captured_dict["mode"].lower()}'
    rest = f'.b32{mode} {d}, {a}, {c}, {b};'
    instr['rest'] = rest


def ptx_sel(kernel, instrs, captured_dict, instr):
    d = ptx_r(captured_dict, 'r0')
    a = ptx_r(captured_dict, 'r8')
    b = ptx_irc(kernel, instrs, captured_dict, instr, 'i20', 'r20')
    c = ptx_p(captured_dict, 'p39')
    instr['op'] = 'selp'
    instr['rest'] = f'.b32 {d}, {a}, {b}, {c};'


def ptx_ldst(kernel, instrs, captured_dict, instr):
    if instr['op'] in ['LDL', 'STL']:
        ss = 'local'
    elif instr['op'] in ['LDS', 'STS']:
        ss = 'shared'
    elif instr['op'] == 'LDC':
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

    d = ptx_r(captured_dict, 'r0')
    d_idx = captured_dict['r0ord']
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
    if ss in ['shared', 'const']:
        a = ptx_r(captured_dict, 'r8')
    else:
        a = ptx_r2d(kernel, instrs, captured_dict, instr, 'r8')
    if a in ['0', '-0', '|0|', '']:
        if ss == 'shared':
            a = '_shared+'
        else:
            a = ''
    else:
        a = f'{a}+'
    b = ptx_i(captured_dict, 'i20w24')
    b = int(b, base=0) if b else 0

    if 'LD' in instr['op']:
        instr['op'] = 'ld'
        dab = f'{d}, [{a}{b}]'
    else:
        instr['op'] = 'st'
        dab = f'[{a}{b}], {d}'

    if not captured_dict['type'] or '32' in captured_dict['type']:
        type_str = 'u32'
        instr['rest'] = f'.{ss}{cache_str}.{type_str} {dab};'
    elif '64' in captured_dict['type']:
        type_str = 'u32'
        instr['rest'] = f'.{ss}{cache_str}.v2.{type_str} {dab};'
    elif '128' in captured_dict['type']:
        type_str = 'u32'
        instr['rest'] = f'.{ss}{cache_str}.v4.{type_str} {dab};'
    else:
        type_str = captured_dict['type'].lower()
        instr['rest'] = f'.{ss}{cache_str}.{type_str} {dab};'


def ptx_atom(kernel, instrs, captured_dict, instr):
    if instr['op'] == 'ATOMS':
        ss = 'shared'
    else:
        ss = 'global'
    op_str = captured_dict['mode'].lower()
    if not captured_dict['type']:
        if op_str in ['or', 'and', 'xor']:
            type_str = 'b32'
        else:
            type_str = 'u32'
    else:
        type_str = captured_dict['type'][1:].lower()
    if '64' in type_str and op_str == 'exch':
        type_str = 'b64'

    if '64' in type_str:
        d = ptx_r2d(kernel, instrs, captured_dict, instr, 'r0')
        b = ptx_r2d(kernel, instrs, captured_dict, instr, 'r20')
        c = ptx_r2d(kernel, instrs, captured_dict, instr, 'r39a')
    else:
        d = ptx_r(captured_dict, 'r0')
        b = ptx_r(captured_dict, 'r20')
        c = ptx_r(captured_dict, 'r39a')

    if ss == 'shared':
        a = ptx_r(captured_dict, 'r8')
    else:
        a = ptx_r2d(kernel, instrs, captured_dict, instr, 'r8')
    if a in ['0', '-0', '|0|', '']:
        if ss == 'shared':
            a = '_shared+'
        else:
            a = ''
    else:
        a = f'{a}+'
    i = ptx_i(captured_dict, 'i20w24')
    i = int(i, base=0) if i else 0

    if c:
        c = f', {c}'
    else:
        c = ''

    if d in ['', '0']:
        instr['op'] = 'red'
        instr['rest'] = f'.{ss}.{op_str}.{type_str} [{a}{i}], {b};'
    else:
        instr['op'] = 'atom'
        instr['rest'] = f'.{ss}.{op_str}.{type_str} {d}, [{a}{i}], {b}{c};'


def ptx_exit(kernel, instrs, captured_dict, instr):
    instr['op'] = 'ret'


def ptx_sync(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bra'
    instr['rest'] = f' {captured_dict["label"]};'


def ptx_brk(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bra'
    instr['rest'] = f' {captured_dict["label"]};'


def ptx_bra(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bra'
    uni = '.uni' if captured_dict['U'] else ''
    instr['rest'] = f'{uni} {captured_dict["label"]};'


def ptx_bar(kernel, instrs, captured_dict, instr):
    instr['op'] = 'bar'
    if captured_dict['i8w8']:
        i_str = ptx_i(captured_dict, 'i8w8')
        instr['rest'] = f'.sync {i_str};'
    else:
        instr['rest'] = instr['rest'].lower()
    pass


def ptx_s2r(kernel, instrs, captured_dict, instr):
    instr['op'] = 'mov'
    r_str = ptx_r(captured_dict, 'r0')
    sr_str = f"%{captured_dict['sr'][3:].lower()}"
    instr['rest'] = f'.b32 {r_str}, {sr_str};'


def ptx_r2p(kernel, instrs, captured_dict, instr):
    a = ptx_r(captured_dict, 'r8')
    b = ptx_i(captured_dict, 'i20')
    b = int(b, base=0) if b else 0
    for i in range(7):
        if b & (1 << i):
            kernel.pred_regs.add(i)
            r_idx = kernel.ptx_reg_count + 256
            r_str = f'%r{r_idx}'
            kernel.reg_set.add(r_idx)
            kernel.ptx_reg_count += 1
            ptx_append_instr(instrs, instr, 'and', f'.b32 {r_str}, {a}, {1 << i};')
            ptx_append_instr(instrs, instr, 'setp', f'.eq.s32 %p{i}, {r_str}, 0;')
    instr['line_num'] = None


grammar_ptx = {
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
    'IADD3': [  # add
        {'rule': rf'IADD3 {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_iadd3}],
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
    'ISETP': [  # setp
        {'rule': rf'ISETP{icmp}{u32}{bool2} {p3}, {p0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {p39};',
         'ptx': ptx_isetp}],
    'ICMP': [  # slct
        {'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_icmp}],
    # Logic and Shift Instructions
    'LOP': [  # and or xor not
        {'rule': rf'LOP{bool_} {r0nc}, (?P<INV8>~)?{r8}, (?P<INV>~)?(?:{r20}|{i20}|{CONST_NAME_RE})(?P<TINV>\.INV)?;',
         'ptx': ptx_lop}],
    'LOP32I': [  # and or xor not
        {'rule': rf'LOP32I{bool2} {r0nc}, (?P<INV8>~)?{r8}, {i20w32};', 'ptx': ptx_lop32i}],
    'LOP3': [  # lop3
        {'rule': rf'LOP3\.LUT {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39}, {i28w8};', 'ptx': ptx_lop3}],
    'SHF': [  # shf shr
        {'rule': rf'SHF\.(?P<lr>[LR]){shf} {r0nc}, {r8}, (?:{r20}|{i20}), {r39};', 'ptx': ptx_shf}],
    'SHL': [  # shl
        {'rule': rf'SHL {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_shl}],
    'SHR': [  # shr
        {'rule': rf'SHR{u32} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_shr}],
    # Movement Instructions
    'MOV': [  # mov
        {'rule': rf'MOV {r0nc}, (?:{r20}|{i20}|{CONST_NAME_RE});', 'ptx': ptx_mov}],
    'MOV32I': [  # mov
        {'rule': rf'MOV32I {r0nc}, {i20w32};', 'ptx': ptx_mov32i},
        {'rule': rf'MOV32I {r0nc}, {GLOBAL_NAME_RE};', 'ptx': ptx_mov32i}],
    'SHFL': [  # shfl.sync
        {'rule': rf'SHFL{shfl} {p48}, {r0nc}, {r8}, (?:{i20w8}|{r20}), (?:{i34w13}|{r39});', 'ptx': ptx_shfl}],
    'PRMT': [  # prmt
        {'rule': rf'PRMT{prmt} {r0nc}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {r39};', 'ptx': ptx_prmt}],
    'SEL': [  # selp
        {'rule': rf'SEL {r0}, {r8}, (?:{r20}|{i20}|{CONST_NAME_RE}), {p39};', 'ptx': ptx_sel}],
    # Predicate/CC Instructions
    'PSETP': [  # setp
        {'rule': rf'PSETP(?:\.(?P<bool>AND|OR|XOR)){bool2} {p3}, {p0}, {p12}, {p29}, {p39};', 'ptx': ptx_psetp}],
    # Compute Load/Store Instructions
    'LDG': [  # ld
        {'rule': rf'LDG{mem_cache}{mem_type} {r0nc}, {addr};', 'ptx': ptx_ldst}],
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
    # ATOM Instructions
    'ATOM': [  # atom
        {'rule': rf'ATOM{atom} {r0nc}, {addr}, {r20}(?:, {r39a})?;', 'ptx': ptx_atom}],
    'ATOMS': [  # atom
        {'rule': rf'ATOMS{atom} {r0nc}, {addr}, {r20}(?:, {r39a})?;', 'ptx': ptx_atom}],
    'RED': [  # red
        {'rule': rf'RED{atom} {addr}, {r20};', 'ptx': ptx_atom}],
    # Control Instructions
    'EXIT': [  # exit
        {'rule': rf'EXIT;', 'ptx': ptx_exit}],
    'BRK': [  # bra
        {'rule': rf'BRK `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_brk}],
    'SYNC': [  # bra
        {'rule': rf'SYNC `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_sync}],
    'BRA': [  # bra
        {'rule': rf'BRA(?P<U>\.U)? `\(\s*{LABEL_RE}\s*\);', 'ptx': ptx_bra}],

    # Miscellaneous Instructions
    'BAR': [  # bar
        {'rule': rf'BAR\.SYNC (?:{i8w8}|{r8});', 'ptx': ptx_bar}],
    'S2R': [  # mov
        {'rule': rf'S2R {r0nc}, {sr};', 'ptx': ptx_s2r}],
    'R2P': [
        {'rule': rf'R2P PR, {r8}, {i20};', 'ptx': ptx_r2p}],
}
