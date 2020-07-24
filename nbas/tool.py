from struct import pack
from subprocess import getstatusoutput
from operator import itemgetter
from typing import List, Any, Union

from .grammar import *


def disassemble_nv(binary, arch, tmp_file='temp.bin'):
    # 使用nvdisasm 反汇编
    with open(tmp_file, 'wb') as f:
        f.write(binary)
    ret, sass = getstatusoutput(f'nvdisasm -b SM{arch} -hex -novliw {tmp_file}')
    os.remove(tmp_file)
    if ret != 0:
        raise Warning(f'{sass}')
    sass = [line for line in sass.split('\n')]
    if len(sass) <= 1:
        raise Warning(f'{sass}')
    return sass


def detect(code, begin, end, arch, tmp_file='temp.bin'):
    # prepare code
    ctrl = encode_ctrl('-:--:-:-:-:1')
    code_group = []
    if arch < 70:
        ctrls = encode_ctrls(ctrl, ctrl, ctrl)
        code |= 0x70000
        code_group = [ctrls, code, 0x50b0000000070f00, 0x50b0000000070f00]
    else:
        code |= ctrl << 105
        code |= 0x7000

    codes = [{'code': code, 'info': 'O---'}]

    length = end - begin
    mask = ((1 << length) - 1) << begin
    if length > 8:
        for i in range(begin, end):
            # ignore Preg
            if (arch < 70 and 16 <= i < 20) or (arch >= 70 and 12 <= i < 16):
                continue
            codes.append({'code': code ^ (1 << i), 'info': f'B{i:#4d}'})
    elif length > 0:
        for i in range(1 << length):
            codes.append({'code': code & (~mask) | i << begin, 'info': f'N{i:#4d}'})

    for i, line in enumerate(codes):
        code = line['code']
        info = line['info']
        if arch < 70:
            code_group[1] = code
            binary = pack(f'<{len(code_group)}Q', *code_group)
        else:
            binary = pack(f'<QQ', code & 0xFFFFFFFFFFFFFFFF, code >> 64)

        try:
            sass = disassemble_nv(binary, arch, tmp_file)
            if arch < 70:
                instr = process_sass_line(sass[2])
            else:
                instr = process_sass_line(sass[1])
                instr = process_sass_code(sass[2], instr)
            code_diff = codes[0]['code']
            if code_diff != code:
                if length > 8:
                    code_diff ^= code
                else:
                    code_diff = code & mask
            if arch < 70:
                print(f'{info} {code:#018x} {code_diff:#018x} {print_instr(instr)}')
            else:
                print(f'{info} {code:#034x} {code_diff:#034x} {print_instr(instr)}')
        except Warning as warn:
            print(f'{warn}')

        if i % 4 == 0:
            print('')


no_dst = ['ST', 'STG', 'STS', 'STL', 'RED']
src_reg = [
    'r8', 'r20', 'r39',  # Pascal
    'p12', 'p29', 'p39', 'p58', 'X',
    'r24', 'r32', 'r64', 'ur24', 'ur32', 'ur64',  # Turing
    'p64q', 'p68', 'p77', 'p87', 'up77', 'up87',
]
dst_reg = [
    'r0',  # Pascal
    'p0', 'p3', 'p45', 'p48', 'p48q', 'CC',
    'r16', 'ur16',  # Turing
    'p81', 'p84', 'up81', 'up84',
]
reg_ops = src_reg + dst_reg

bad_val = ['RZ', 'PT', 'URZ', 'UPT', None]

ordered_op = [
    'BRA', 'BRX', 'JMP', 'JMX', 'SSY', 'SYNC', 'CAL', 'JCAL', 'PRET', 'RET', 'BRK', 'PBK', 'CONT', 'PCNT',  # Pascal
    'EXIT', 'PEXIT', 'BPT', 'NOP', 'B2R', 'BAR', 'R2B', 'DEPBAR',
    # 'VOTE',
    'BMOV', 'BPT', 'BREAK', 'BRXU', 'BSSY', 'BSYNC', 'CALL', 'JMXU', 'KILL', 'NANOSLEEP', 'RPCMOV', 'RTT',  # Turing
    'WARPSYNC', 'YIELD', 'GETLMEMBASE', 'LEPC', 'PMTRIG', 'SETCTAID', 'SETLMEMBASE',
    # 'VOTEU',
]

SR_op = ['CS2R', 'S2R', 'S2UR']


def count_unique_descendants(node, edges):
    if children := node['children']:
        for child in children:  # skip WaR deps and traversed edges
            if not child[1]:
                continue
            k = f'{node["line_num"]}^{child[0]["line_num"]}'
            if k not in edges:
                edges[k] = 0
            else:
                edges[k] += 1
                continue
            for line_num in count_unique_descendants(child[0], edges):
                if line_num not in node['deps']:
                    node['deps'][line_num] = 0
                node['deps'][line_num] += 1
        for child in children:  # WaR deps
            if child[1]:
                continue
            k = f'{node["line_num"]}^{child[0]["line_num"]}'
            if k not in edges:
                edges[k] = 0
            else:
                edges[k] += 1
                continue
            count_unique_descendants(child[0], edges)
    else:
        return [node['line_num'], ]
    return [node['line_num'], *(node['deps'].keys())]


def update_dep_counts(node, edges):
    if children := node['children']:
        for child in children:
            k = f'{node["line_num"]}^{child[0]["line_num"]}'
            if k not in edges:
                edges[k] = 0
            else:
                edges[k] += 1
                continue
            update_dep_counts(child[0], edges)
    if type(node['deps']) is dict:
        node['deps'] = len(node['deps'])


def schedule_61(instrs):
    for instr in instrs:
        instr['ctrl'] = encode_ctrl(instr['ctrl'])

        # if the first instruction in the block is waiting on a dep, it should go first.
        instr['first'] = 1 if (instr['ctrl'] & 0x1f800) else 0

        instr['exe_time'] = 0

        # ORDERED flag should be set when preprocess, before this function.
        if 'order' not in instr:
            instr['order'] = 0
        instr['force_stall'] = (instr['ctrl'] & 0xf)
        instr['children'] = []
        instr['parents'] = 0

    reads = {}
    writes = {}
    ready = []
    schedule = []
    ordered_parent = {}
    # assemble the instructions to op codes
    for instr in instrs:
        op = instr['op']
        rest = instr['rest']
        gram = None
        captured_dict = None
        for g in grammar_61[op]:
            if m := re.search(g['rule'], op + rest):
                gram = g
                captured_dict = m.groupdict()
                break
        if not captured_dict:
            raise Exception(f'Cannot recognize instruction {op + rest}')
        src = []
        dst = []
        # copy over instruction types for easier access
        instr = {**instr, **gram['type']}

        instr['dual_cnt'] = instr['dual']

        # A predicate prefix is treated as a source reg
        if instr['pred']:
            src.append(instr['pred_reg'])

        # Handle P2R and R2P specially
        if op in ['R2P', 'P2R'] and captured_dict['i20']:
            list_ = src if op == 'P2R' else dst
            mask = int(captured_dict['i20'], base=0)
            for i in range(7):
                if mask & (1 << i):
                    list_.append(f'P{i}')
                # make this instruction dependent on any predicates it's not setting
                # this is to prevent a race condition for any predicate sets that are pending
                elif op == 'R2P':
                    src.append(f'P{i}')
            instr['no_dual'] = 1

        # Populate our register source and destination lists, skipping any zero or true values
        for operand in captured_dict:
            if operand not in reg_ops:
                continue
            # figure out which list to populate
            list_ = dst if operand in dst_reg and op not in no_dst else src

            # Filter out RZ and PT
            bad_val = 'RZ' if 'r' in operand else 'PT'

            if opr := captured_dict[operand] != bad_val:
                if 'r0' == operand:
                    # todo: 判断vector
                    pass
                elif 'r8' == operand:
                    # todo: 判断addr vector
                    pass
                elif operand in ['CC', 'X']:
                    list_.append('CC')
                else:
                    list_.append(opr)
        instr['const'] = 1 if 'c20' in captured_dict or 'c39' in captured_dict else 0

        # Find Read-After-Write dependencies
        for operand in src:
            if operand not in writes:
                continue
            # Memory operations get delayed access to registers but not to the predicate
            reg_latency = instr['rlat'] if src != instr['pred_reg'] else 0

            for parent in writes[operand]:
                # add this instruction as a child of the parent
                # set the edge to the total latency of reg source availability
                latency = 13 if re.match('^P\d', operand) else parent['lat']
                parent['children'].append([instr, latency - reg_latency])
                instr['parents'] += 1

                # if the destination was conditionally executed, we also need to keep going back till it wasn't
                if not parent['pred']:
                    break

        # Find Write-After-Read dependencies
        for operand in dst:
            if operand not in reads:
                continue
            # Flag this instruction as dependent to any previous read
            for reader in reads[operand]:
                # no need to stall for these types of dependencies
                reader['children'].append([instr, 0])
                instr['parents'] += 1

            # Once dependence is marked we can clear out the read list (unless this write was conditional).
            # The assumption here is that you would never want to write out a register without
            # subsequently reading it in some way prior to writing it again.
            if not instr['pred']:
                del reads[operand]

        # Enforce instruction ordering where requested
        if instr['order']:
            if ordered_parent and instr['order'] > ordered_parent['order']:
                ordered_parent['children'].append([instr, 0])
                instr['parents'] += 1
            ordered_parent = instr
        elif ordered_parent:
            ordered_parent = {}

        # For a dest reg, push it onto the write stack
        for operand in dst:
            if operand not in writes:
                writes[operand] = []
            writes[operand].insert(0, instr)

        # For a src reg, push it into the read list
        for operand in src:
            if operand not in reads:
                reads[operand] = []
            reads[operand].append(instr)

        # if this instruction has no dependencies it's ready to go
        if not instr['parents']:
            ready.append(instr)

    if ready:
        # update dependent counts for sorting hueristic
        ready_parent = {
            'children': [[x, 1] for x in ready],
            'inst': 'root'
        }

        count_unique_descendants(ready_parent, {})
        update_dep_counts(ready_parent, {})

        ready.sort(key=itemgetter('first', 'deps', 'dual_cnt', 'line_num'))

    # Process the ready list, adding new instructions to the list as we go.
    clock = 0

    while instruct := ready.pop(0):
        stall = instruct['stall']
        # apply the stall to the previous instruction
        if schedule and stall < 16:
            prev = schedule[-1]

            if prev['force_stall'] > stall:
                stall = prev['force_stall']

            # if stall is greater than 4 then also yield
            # the yield flag is required to get stall counts 12-15 working correctly.
            prev['ctrl'] &= 0x1ffe0 if stall > 4 else 0x1fff0
            prev['ctrl'] |= stall
            clock += stall
        # For stalls bigger than 15 we assume the user is managing it with a barrier
        else:
            instruct['ctrl'] &= 0x1fff0
            instruct['ctrl'] |= 1
            clock += 1

        # add a new instruction to the schedule
        schedule.append(instruct)

        # update each child with a new earliest execution time
        if children := instruct['children']:
            for child, latency in children:
                # update the earliest clock value this child can safely execute
                earliest = clock + latency
                if child['exe_time'] < earliest:
                    child['exe_time'] = earliest
                # decrement parent count and add to ready queue if none remaining.
                child['parents'] -= 1
                if child['parents'] < 1:
                    ready.append(child)
            instruct['children'] = []

        # update stall and mix values in the ready queue on each iteration
        for instr in ready:
            # calculate how many instructions this would cause the just added instruction to stall.
            stall = instr['exe_time'] - clock
            if stall < 1:
                stall = 1

            # if using the same compute resource as the prior instruction then limit the throughput
            if instr['class'] == instruct['class']:
                if stall < instr['tput']:
                    stall = instr['tput']

            # dual issue with a simple instruction (tput <= 2)
            # can't dual issue two instructions that both load a constant
            elif instr['dual'] and not instruct['dual'] and instruct['tput'] <= 2 and not instruct[
                'no_dual'] and stall == 1 and instr['exe_time'] <= clock and not instr['const'] and instruct['const']:
                stall = 0

            instr['stall'] = stall

            # add an instruction class mixing huristic that catches anything not handled by the stall
            instr['mix'] = 1 if instr['class'] != instruct['class'] else 0
            if instr['mix'] and instr['op'] == 'R2P':
                instr['mix'] = 2

        # sort the ready list by stall time, mixing huristic, dependencies and line number
        ready.sort(key=itemgetter('first', 'stall', 'dual_cnt', 'mix', 'deps', 'line_num'))

        for instr in ready:
            if instr['dual_cnt'] and instr['stall'] == 1:
                instr['dual_cnt'] = 0

    return schedule


def schedule_75(instrs):
    blocks = []

    block = []
    for instr in instrs:
        instr.update(decode_ctrl(encode_ctrl(instr['ctrl'])))

        instr['exe_time'] = 0

        # check schedule flag
        instr['schedule'] = 0 if instr['ctrl'].startswith('K') else 1

        instr['children'] = []
        instr['parents'] = 0
        instr['deps'] = {}

        op = instr['op']
        rest = instr['rest']
        if (op in ordered_op) or ((op in SR_op) and ('SR_CLOCK' in rest)) or instr['schedule'] == 0:
            if block:
                blocks.append(block)
            blocks.append([instr, ])
            block = []
        else:
            block.append(instr)

    schedule = []
    clock = 0

    for block in blocks:
        reads = {}
        writes = {}
        ready = []

        # assemble the instructions to op codes
        for instr in block:
            op = instr['op']
            rest = instr['rest']
            grams = grammar_75[op]
            gram = None
            captured_dict = None
            for g in grams:
                m = re.search(g['rule'], op + rest)
                if m:
                    gram = g
                    captured_dict = m.groupdict()
                    break
            if not gram:
                raise Exception(f'Cannot recognize instruction {op + rest}')

            src = []
            dst = []
            # copy over instruction types for easier access
            instr = {**instr, **instr_type_75[gram['type']], 'class': gram['type']}

            # A predicate prefix is treated as a source reg
            if instr['pred']:
                src.append(instr['pred_reg'])

            # Populate our register source and destination lists, skipping any zero or true values
            for operand in captured_dict:
                if operand not in reg_ops:
                    continue
                # figure out which list to populate
                list_: list = dst if (operand in dst_reg and op not in no_dst) else src

                # Filter out RZ and PT
                if (opr := captured_dict[operand]) not in bad_val:
                    if operand in ['CC', 'X']:
                        list_.append('CC')
                    # todo: 判断vector 和 64位addr
                    # 需要根据具体指令判断src和dst，比如LDG，SHF F2I等等
                    # elif operand in ['r16', 'ur16']:
                    #     r_num = int(captured_dict[operand].strip('UR'))
                    #     list_.append(opr)
                    #     if type_ := (captured_dict['type'] if 'type' in captured_dict else None):
                    #         if '64' in type_:
                    #             list_.append(re.sub('\d+', f'{r_num+1}', opr))
                    #         elif '128' in type_:
                    #             list_.append(re.sub('\d+', f'{r_num + 1}', opr))
                    #             list_.append(re.sub('\d+', f'{r_num + 2}', opr))
                    #             list_.append(re.sub('\d+', f'{r_num + 3}', opr))
                    #     pass
                    else:
                        list_.append(opr)
            instr['const'] = 1 if 'c40neg' in captured_dict else 0

            # Find Read-After-Write dependencies
            for operand in src:
                if operand not in writes:
                    continue
                # Memory operations get delayed access to registers but not to the predicate
                reg_latency = instr['rlat'] if src != instr['pred_reg'] else 0

                for parent in writes[operand]:
                    # add this instruction as a child of the parent
                    # set the edge to the total latency of reg source availability
                    # latency = 13 if re.match('^U?P\d', operand) else parent['lat']
                    latency = parent['lat']
                    parent['children'].append([instr, latency - reg_latency])
                    instr['parents'] += 1

                    # if the destination was conditionally executed, we also need to keep going back till it wasn't
                    if not parent['pred']:
                        break

            # Find Write-After-Read dependencies
            for operand in dst:
                if operand not in reads:
                    continue
                # Flag this instruction as dependent to any previous read
                for reader in reads[operand]:
                    # no need to stall for these types of dependencies
                    reader['children'].append([instr, 0])
                    instr['parents'] += 1

                # Once dependence is marked we can clear out the read list (unless this write was conditional).
                # The assumption here is that you would never want to write out a register without
                # subsequently reading it in some way prior to writing it again.
                if not instr['pred']:
                    del reads[operand]

            # For a dest reg, push it onto the write stack
            for operand in dst:
                if operand not in writes:
                    writes[operand] = []
                writes[operand].insert(0, instr)

            # For a src reg, push it into the read list
            for operand in src:
                if operand not in reads:
                    reads[operand] = []
                reads[operand].append(instr)

            # if this instruction has no dependencies it's ready to go
            if not instr['parents']:
                ready.append(instr)

        if ready:
            # update dependent counts for sorting hueristic
            ready_parent = {
                'children': [[x, 1] for x in ready],
                'inst': 'root',
                'line_num': '',
                'deps': {},
            }

            count_unique_descendants(ready_parent, {})
            update_dep_counts(ready_parent, {})

            ready.sort(key=itemgetter('line_num'))
            ready.sort(key=itemgetter('deps'), reverse=True)

        # Process the ready list, adding new instructions to the list as we go.

        while ready:
            instruct = ready.pop(0)
            stall = instruct['stall']
            # apply the stall to the previous instruction
            if schedule and stall < 16:
                prev = schedule[-1]

                # if stall is greater than 4 then also yield
                # the yield flag is required to get stall counts 12-15 working correctly.
                prev['yield'] = 0 if stall > 4 else 1
                prev['stall'] = stall
            # For stalls bigger than 15 we assume the user is managing it with a barrier
            else:
                instruct['stall'] = 1
            clock += stall

            # add a new instruction to the schedule
            schedule.append(instruct)

            # update each child with a new earliest execution time
            if children := instruct['children']:
                for child, latency in children:
                    # update the earliest clock value this child can safely execute
                    earliest = clock + latency
                    if child['exe_time'] < earliest:
                        child['exe_time'] = earliest
                    # decrement parent count and add to ready queue if none remaining.
                    child['parents'] -= 1
                    if child['parents'] < 1:
                        ready.append(child)
                instruct['children'] = []

            # update stall and mix values in the ready queue on each iteration
            for instr in ready:
                # calculate how many instructions this would cause the just added instruction to stall.
                stall = instr['exe_time'] - clock
                if stall < 1:
                    stall = 1

                # if using the same compute resource as the prior instruction then limit the throughput
                if instr['class'] == instruct['class']:
                    if stall < instr['tput']:
                        stall = instr['tput']

                instr['stall'] = stall

                # add an instruction class mixing huristic that catches anything not handled by the stall
                instr['mix'] = 1 if instr['class'] != instruct['class'] else 0
                if instr['mix'] and instr['op'] == 'R2P':
                    instr['mix'] = 2

            # sort the ready list by stall time, mixing huristic, dependencies and line number
            ready.sort(key=itemgetter('line_num'))
            ready.sort(key=itemgetter('mix', 'deps'), reverse=True)
            ready.sort(key=itemgetter('stall'))

    # for instr in schedule:
    #     instr['ctrl'] = print_ctrl(instr)

    return schedule
