from .elf import *
from .tool import *
from .ptx import *


class Data:
    def __init__(self, iterable=(), **kwargs):
        self.name = b''
        # global constant constant2
        self.type = 'global'
        self.align = 0
        self.offset = 0
        self.size = 0
        self.binary = b''

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        msg = f'Name:{self.name.decode()}, Type:{self.type}, Align:{self.align}, Offset:{self.offset}, Size:{self.size}'
        return msg

    def __eq__(self, other):
        if self.__dict__ != other.__dict__:
            print(f'old: {self}')
            print(f'new: {other}')
        return self.__dict__ == other.__dict__

    def print(self):
        asm = ''
        asm += f".{self.type}: {self.name.decode()} # Size:{self.size}, Offset:{self.offset}\n"
        asm += f"    .align {self.align}\n"
        binary = self.binary
        if binary:
            length = 16
            for i in range(0, len(binary), length):
                s = binary[i:i + length]
                asm += f'    /*{i * length:04x}*/ .byte ' + ', '.join([f'{b:#04x}' for b in s]) + ',\n'
        else:
            asm += f"    .zero {self.size}\n"
        # asm += f".end_{self.type}\n"
        return asm

    def print_ptx(self):
        if self.type == 'global':
            type_ = 'global'
        elif self.type == 'constant':
            type_ = 'const'
        else:
            return ''

        ptx = ''
        ptx += f".{type_} .align {self.align} .b8 {self.name.decode()}[{self.size}]"
        binary = self.binary
        if binary:
            length = 16
            ptx += ' = {\n'
            for i in range(0, len(binary), length):
                s = binary[i:i + length]
                ptx += f'    /*{i * length:04x}*/ ' + ', '.join([f'{b:#04x}' for b in s]) + ',\n'
            ptx = ptx[:-2]
            ptx += '\n};\n'
        else:
            ptx += f";\n"
        return ptx


class Kernel:
    EIATTR = {
        'CTAIDZ_USED': b'\x01\x04',
        # nvcc compile with "-Xptxas -dlcm=ca"
        'EXPLICIT_CACHING': b'\x01\x21',
        'SW1850030_WAR': b'\x01\x2a',
        'WMMA_USED': b'\x01\x2b',
        'SW2393858_WAR': b'\x01\x30',
        'SW2861232_WAR': b'\x01\x35',
        'CBANK_PARAM_SIZE': b'\x03\x19',
        'MAXREG_COUNT': b'\x03\x1b',
        'MAX_THREADS': b'\x04\x05',
        'PARAM_CBANK': b'\x04\x0a',
        'REQNTID': b'\x04\x10',
        'KPARAM_INFO': b'\x04\x17',
        'EXIT_INSTR_OFFSETS': b'\x04\x1c',
        'S2RCTAID_INSTR_OFFSETS': b'\x04\x1d',
        'CRS_STACK_SIZE': b'\x04\x1e',
        'COOP_GROUP_INSTR_OFFSETS': b'\x04\x28',
        'INT_WARP_WIDE_INSTR_OFFSETS': b'\x04\x31',
        'INDIRECT_BRANCH_TARGETS': b'\x04\x34',  # CUDA 11.0新出现的，记录了SYNC, BRX BRA指令的跳转地址
        'SW_WAR': b'\x04\x36',  # CUDA 11.1新出现的, 不知道干啥的
        'CUDA_API_VERSION': b'\x04\x37',  # CUDA 11.1新出现的，CUDA版本 0x6F = 111
    }
    EIATTR_STR = {val: key for (key, val) in EIATTR.items()}

    CONST0_STR_61 = {
        0x8: 'BLOCK_DIM_X',
        0xc: 'BLOCK_DIM_Y',
        0x10: 'BLOCK_DIM_Z',
        0x14: 'GRID_DIM_X',
        0x18: 'GRID_DIM_Y',
        0x1c: 'GRID_DIM_Z',
        0x20: 'STACK',
        0x28: 'GRID_ID_LO',
        0x2c: 'GRID_ID_HI',
        0xfc: 'DYN_SMEM_SIZE',
        0xd0: 'CONST3_ADDR_LO',
        0xd4: 'CONST3_ADDR_HI',
    }

    for i in range(32):
        CONST0_STR_61[0x30 + i * 4] = f'ENV_REG_{i}'
    CONST0_VAL_61 = {val: key for (key, val) in CONST0_STR_61.items()}

    CONST0_STR_75 = {
        0x0: 'BLOCK_DIM_X',
        0x4: 'BLOCK_DIM_Y',
        0x8: 'BLOCK_DIM_Z',
        0xc: 'GRID_DIM_X',
        0x10: 'GRID_DIM_Y',
        0x14: 'GRID_DIM_Z',
        0x28: 'STACK',
        0x30: 'GRID_ID_LO',
        0x34: 'GRID_ID_HI',
        0x2c: 'DYN_SMEM_SIZE',
        0x10c: 'N_SIMD',
    }

    for i in range(32):
        CONST0_STR_75[0x88 + i * 4] = f'ENV_REG_{i}'
    CONST0_VAL_75 = {val: key for (key, val) in CONST0_STR_75.items()}

    def __init__(self, iterable=(), **kwargs):
        self.name = b''
        self.linkage = 0
        self.bar_count = 0
        self.reg_count = 0
        self.reg_map = {}
        self.ptx_reg_count = 0
        self.ptx_pred_reg_count = 0
        self.reg_set = set()
        self.pred_regs = set()
        self.pred_reg_count = 0
        self.reg64_count = 0
        # 以下3个size和stack, lobal用量有关
        self.frame_size = 0
        self.min_stack_size = 0
        self.max_stack_size = 0
        self.shared_size = 0
        self.param_base = 0xffff
        self.param_size = 0
        # ordinal, param_offset, param_size, param_align
        self.params = []

        self.maxreg_count = 0
        # block_dim_x, block_dim_y, block_dim_z
        self.max_threads = [0, 0, 0]
        self.ctaid_offsets = []
        self.exit_offsets = []
        self.coop_group_instr_offsets = []
        self.int_warp_wide_instr_offsets = []
        self.indirect_branch_targets = []
        self.reqntid = [0, 0, 0]
        self.ctaidz_used = False
        self.explicit_caching = False
        self.crs_stack_size = 0

        self.sw1850030_war = False
        self.sw2393858_war = False
        self.sw2861232_war = False
        self.wmma_used = False

        # Relocation info
        self.rels = []
        self.rel_map = {}
        self.consts = set()
        self.globals = set()

        self.asm = ''
        # line_num ctrl pred pred_not pred_reg op rest label
        self.instrs = []
        self.binary = b''
        self.arch = 61
        self.cuda_api_version = 111
        self.sw_war = 0

        self.section = None
        self.shared_section = None
        self.constant0_section = None
        self.constant0_size = 0
        self.constant2_section = None
        self.constant2 = None
        self.info_section = None
        self.rel_section = None
        self.symbol_idx = 0

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        linkage = Symbol.STB_STR[self.linkage]
        msg = f'Name:{self.name.decode()}, Linkage:{linkage}, Registers:{self.reg_count}, Stack:{self.frame_size}, ' \
              f'SharedMem:{self.shared_size}, Barriers:{self.bar_count}, ' \
              f'Size:{self.section.sh_size if self.section else 0}, ' \
              f'Params:{self.params}'
        return msg

    def print_meta(self):
        asm = ''
        asm += f'.kernel: {self.name.decode()}\n'
        asm += f'    # Linkage: {Symbol.STB_STR[self.linkage]}\n'
        asm += f'    # Registers: {self.reg_count}\n'
        asm += f'    # Barriers: {self.bar_count}\n'
        if self.section:
            asm += f'    # Size: {self.section.sh_size}\n'
        asm += f'    # Constant0: {self.constant0_size}\n'
        asm += f'    # min_stack_size: {self.min_stack_size}, max_stack_size: {self.max_stack_size}\n'
        if self.instrs and self.coop_group_instr_offsets:
            ops = set()
            for offset in self.coop_group_instr_offsets:
                instr = self.instrs[addr2line_num(offset, self.arch)]
                ops.add(instr['op'])
            asm += f'    # coop_group_instr_offsets: {", ".join(ops)}\n'

        if self.instrs and self.int_warp_wide_instr_offsets:
            ops = set()
            for offset in self.int_warp_wide_instr_offsets:
                instr = self.instrs[addr2line_num(offset, self.arch)]
                ops.add(instr['op'])
            asm += f'    # int_warp_wide_instr_offsets: {", ".join(ops)}\n'
        if self.sw_war:
            asm += f'    .sw_war {self.sw_war}\n'
        if self.sw1850030_war:
            asm += f'    .sw1850030_war\n'
        if self.sw2393858_war:
            asm += f'    .sw2393858_war\n'
        if self.sw2861232_war:
            asm += f'    .sw2861232_war\n'
        if self.explicit_caching:
            asm += f'    .explicit_caching\n'
        if self.crs_stack_size:
            asm += f'    .crs_stack_size {self.crs_stack_size}\n'
        if self.frame_size:
            asm += f'    .stack {self.frame_size}\n'
        if self.maxreg_count:
            asm += f'    .max_registers {self.maxreg_count}\n'
        if self.max_threads != [0, 0, 0]:
            asm += "    .max_threads {}, {}, {}\n".format(*self.max_threads)
        if self.reqntid != [0, 0, 0]:
            asm += "    .threads {}, {}, {}\n".format(*self.reqntid)
        if self.shared_size:
            asm += f'    .shared {self.shared_size}\n'
        # asm += f'.param\n'
        for param in self.params:
            asm += f"    .param {param['Ordinal']}, ARG_{param['Ordinal']}, c[0x0][{param['Offset']:#0x}], " \
                   f"{param['Size']:3d} # Align:{param['Align']}\n"
        # asm += f'.end_param\n'
        return asm

    @staticmethod
    def print_asm_line(instr):
        # ctrl, addr, pred, op, rest, code, reuse
        asm = ''
        if instr['label']:
            asm += f"{instr['label']}:\n"
        if 'addr' in instr:
            asm += f"    /*{instr['addr']}*/  {instr['ctrl']} {print_instr(instr):<56s} /* {instr['code']} */ " \
                   f"# {print_reuse(instr['reuse'])}"
        else:
            asm += f"    {instr['ctrl']} {print_instr(instr):<56s} # {print_reuse(instr['reuse'])}"
        return asm

    def print_asm(self):
        asm = ''
        for instr in self.instrs:
            asm += self.print_asm_line(instr) + '\n'

        return asm

    def print(self):
        constant2 = ''
        if self.constant2:
            constant2 = self.constant2.print()
        asm = constant2 + self.print_meta() + self.print_asm()

        return asm

    @staticmethod
    def print_ptx_line(instr):
        if instr['line_num'] is None:
            return f"  //{print_instr(instr)}"

        ptx = ''
        if instr['label']:
            ptx += f"{instr['label']}:\n"
        if instr['line_num'] < 0:
            ptx += f"  /*{print_instr(instr)}*/"
        else:
            ptx += f"    {print_instr(instr)}"
        return ptx

    def print_ptx(self):
        ptx = f'.visible .entry {self.name.decode()}(\n'
        ptx += ',\n'.join([f"    .param .b8 PARAM{param['Ordinal']}[{param['Size']}]" for param in self.params])
        ptx += '\n)\n'

        if self.maxreg_count:
            ptx += f'.maxnreg {self.maxreg_count}\n'
        if self.max_threads != [0, 0, 0]:
            ptx += ".maxntid {}, {}, {}\n".format(*self.max_threads)
        if self.reqntid != [0, 0, 0]:
            ptx += ".reqntid {}, {}, {}\n".format(*self.reqntid)
        # .minnctapersm

        ptx += '{\n'
        if self.pred_reg_count:
            ptx += f'    .reg .pred  %p<{self.pred_reg_count}>;\n'
        if self.reg_count:
            ptx += f'    .reg .b32   %r<{self.reg_count}>;\n'
        if self.reg64_count:
            ptx += f'    .reg .b64   %rd<{self.reg64_count}>;\n'
        if self.shared_size:
            ptx += f'    .shared .b8 _shared[{self.shared_size}];\n'
        for instr in self.instrs:
            statement = self.print_ptx_line(instr)
            if statement:
                ptx += statement + '\n'
        ptx += '}\n'

        return ptx

    def unmap_reg(self):
        def unmap_regs(x):
            reg_str = x.group()
            if reg_str in self.reg_map:
                return self.reg_map[reg_str]
            else:
                return reg_str

        for instr in self.instrs:
            instr['rest'] = re.sub(REG_NAME_RE, unmap_regs, instr['rest'])
            if m := re.search(REG_NAME_RE, instr['pred']):
                reg_str = m.group()
                instr['pred'] = instr['pred'].replace(reg_str, self.reg_map[reg_str])
                x = re.search(PRED_RE, instr['pred'])
                instr['pred_reg'] = x.group('pred_reg')

    def mark_const2(self, replace=False):
        def map_const2(x):
            offset = int(x.group('offset'), 0)
            if offset < self.constant2.size:
                num = unpack('I', self.constant2.binary[offset:offset + 4])[0]
                if replace:
                    return f'{num:#0x}'
                return f'/*{num:#0x}*/c[0x2][{offset:#0x}]'
            else:
                return f'c[0x2][{offset:#0x}]'

        for instr in self.instrs:
            instr['rest'] = re.sub(rf'(?P<c>c\[0x2\]\s*\[(?P<offset>{hexx})\])',
                                   map_const2, instr['rest'])

    def map_constant0(self):
        const0_map = self.CONST0_STR_61.copy() if self.arch < 70 else self.CONST0_STR_75.copy()
        for p in self.params:
            begin = p['Offset']
            end = begin + p['Size']
            ordinal = p['Ordinal']
            for i in range(begin, end):
                const0_map[i] = f'ARG_{ordinal}+{i - begin}'

        def map_constants(x):
            offset = int(x.group('offset'), 0)
            if offset in const0_map:
                return f'c[{const0_map[offset]}]'
            else:
                return f'c[0x0][{offset:#0x}]'

        for instr in self.instrs:
            instr['rest'] = re.sub(rf'(?P<c>c\[0x0\]\s*\[(?P<offset>{hexx})\])',
                                   map_constants, instr['rest'])

    def unmap_constant0(self):
        const0_dict = self.CONST0_VAL_61.copy() if self.arch < 70 else self.CONST0_VAL_75.copy()
        for p in self.params:
            begin = p['Offset']
            end = begin + p['Size']
            ordinal = p['Ordinal']
            p_name = p['Name']
            for i in range(begin, end):
                if p_name:
                    const0_dict[f'{p_name}+{i - begin}'] = i
                else:
                    const0_dict[f'ARG_{ordinal}+{i - begin}'] = i

        def unmap_constants(x):
            name = x.group('const')
            if name in const0_dict:
                return f'c[0x0][{const0_dict[name]:#0x}]'
            else:
                return f'c[{name}]'

        for instr in self.instrs:
            instr['rest'] = re.sub(rf'{CONST_NAME_RE}', unmap_constants, instr['rest'])

    def map_global(self):
        for rel in self.rels:
            line_num = addr2line_num(rel.r_offset, self.arch)
            instr = self.instrs[line_num]
            instr['rest'] = instr['rest'].replace('0x0', f'{Relocation.R_TYPE[rel.type]}({rel.sym_name.decode()})')
            self.globals.add(rel.sym_name)

    def unmap_global(self):
        if self.rels:
            self.rels = []
        for i, instr in enumerate(self.instrs):
            m = re.search(GLOBAL_NAME_RE, instr['rest'])
            if m:
                match = m.group()
                type_ = m.group('type')
                name = m.group('name').encode()
                rel = Relocation()
                rel.r_offset = line_num2addr(i, self.arch)
                if self.arch < 70:
                    rel.type = Relocation.R_TYPE_VAL_61[type_]
                else:
                    rel.type = Relocation.R_TYPE_VAL_75[type_]
                rel.sym_name = name
                self.rels.append(rel)
                self.rel_map[i] = rel
                instr['rest'] = instr['rest'].replace(match, '0x0')

    def map_jump(self, rel=False):
        labels = {}
        sync_label = ''
        brk_label = ''
        has_brx = False
        jump_op = jump_op_61 if self.arch < 70 else jump_op_75
        for instr in self.instrs:
            op = instr['op']
            rest = instr['rest']
            if op in jump_op and '0x0;' not in rest:
                address = get_jump_offset(rest)
                line_num = addr2line_num(address, self.arch)
                if rel and (op in rel_jump_op_61 + rel_jump_op_75):
                    line_num += instr['line_num'] + 1
                if line_num not in labels:
                    label = f'L_{len(labels)}'
                    labels[line_num] = label
                else:
                    label = labels[line_num]
                if op == 'SSY':
                    sync_label = label
                elif op == 'PBK':
                    brk_label = label
                instr['rest'] = re.sub(rf'\s+{i20w24}', f' `({label})', rest)
            elif op == 'SYNC':
                instr['rest'] = f' `({sync_label});'
            elif op == 'BRK':
                instr['rest'] = f' `({brk_label});'
            elif op == 'BRX':
                has_brx = True
        if has_brx:
            print(f'Warning: ({self.name.decode()}) BRX instruction found, SYNC and BRX label may be wrong.')
        for line_num, label in labels.items():
            self.instrs[line_num]['label'] = label

    def unmap_jump(self):
        labels = {}
        jump_op = jump_op_61 if self.arch < 70 else jump_op_75
        jump_instrs = []
        for instr in self.instrs:
            label = instr['label']
            op = instr['op']
            if label:
                labels[label] = instr['line_num']
            if op in jump_op:
                jump_instrs.append(instr)
            elif op == 'SYNC':
                instr['rest'] = ';'
            elif op == 'BRK':
                instr['rest'] = ';'

        # Unmap labels
        for instr in jump_instrs:
            op = instr['op']
            rest = instr['rest']
            m = re.search(rf'{LABEL_RE}', rest)
            if m is None:
                raise Exception(f'Cannot recognize jump label {op + rest}')
            label = m.group('label')
            line_num = labels[label]
            offset = line_num2addr(line_num, self.arch)
            if self.arch < 70:
                if line_num % 3 == 0:
                    offset -= 0x8
                if op in rel_jump_op_61:
                    line_num = instr['line_num']
                    offset_src = line_num2addr(line_num, self.arch)
                    offset = offset - (offset_src + 0x8)
            else:
                if op in rel_jump_op_75:
                    line_num = instr['line_num']
                    offset_src = line_num2addr(line_num, self.arch)
                    offset = offset - (offset_src + 0x10)
            instr['rest'] = re.sub(rf'`\(\s*{LABEL_RE}\s*\)', hex(offset), rest)

        for line_num in labels.values():
            self.instrs[line_num]['label'] = ''

    def load_info(self, info_section):
        self.info_section = info_section
        self.params = []
        offset = 0
        while offset < self.info_section.sh_size:
            code, size = unpack('2sH', self.info_section.data[offset:offset + 4])
            offset += 4
            if code == self.EIATTR['CTAIDZ_USED']:
                self.ctaidz_used = True
                size = 0
            elif code == self.EIATTR['EXPLICIT_CACHING']:
                self.explicit_caching = True
                size = 0
            elif code == self.EIATTR['WMMA_USED']:
                self.wmma_used = True
                size = 0
            elif code == self.EIATTR['SW1850030_WAR']:
                self.sw1850030_war = True
                size = 0
            elif code == self.EIATTR['SW2393858_WAR']:
                self.sw2393858_war = True
                size = 0
            elif code == self.EIATTR['SW2861232_WAR']:
                self.sw2861232_war = True
                size = 0
            elif code == self.EIATTR['CBANK_PARAM_SIZE']:
                if not self.param_size:
                    self.param_size = size
                elif size != self.param_size:
                    print(f'Warning: param size not match: {self.param_size} != {size}')
                size = 0
            elif code == self.EIATTR['MAXREG_COUNT']:
                self.maxreg_count = size
                size = 0
            elif code == self.EIATTR['MAX_THREADS']:
                block_dim_x, block_dim_y, block_dim_z = unpack(
                    'III', self.info_section.data[offset:offset + size])
                self.max_threads = [block_dim_x, block_dim_y, block_dim_z]
            elif code == self.EIATTR['PARAM_CBANK']:
                symbol_idx, param_base, param_size = unpack(
                    'IHH', self.info_section.data[offset:offset + size])
                # self.symbol_idx = symbol_idx
                self.param_base = param_base
                if not self.param_size:
                    self.param_size = param_size
                elif param_size != self.param_size:
                    print(f'Warning: param_size not match: {self.param_size} != {param_size}')
            elif code == self.EIATTR['KPARAM_INFO']:
                index, ordinal, param_offset, param_flag = unpack(
                    'IHHI', self.info_section.data[offset:offset + size])
                param_size = param_flag >> 18
                param_align = 1 << (param_flag & 0x3ff) if param_flag & 0x400 else 0
                self.params.append({
                    'Ordinal': ordinal,
                    'Offset': param_offset,
                    'Size': param_size,
                    'Align': param_align
                })
                assert (param_align == 0)
            elif code == self.EIATTR['CRS_STACK_SIZE']:
                self.crs_stack_size = unpack(f'I', self.info_section.data[offset:offset + size])[0]
            elif code == self.EIATTR['REQNTID']:
                block_dim_x, block_dim_y, block_dim_z = unpack(
                    'III', self.info_section.data[offset:offset + size])
                self.reqntid = [block_dim_x, block_dim_y, block_dim_z]
            elif code == self.EIATTR['EXIT_INSTR_OFFSETS']:
                cnt = size // 4
                self.exit_offsets = unpack(f'{cnt}I', self.info_section.data[offset:offset + size])
            elif code == self.EIATTR['S2RCTAID_INSTR_OFFSETS']:
                cnt = size // 4
                self.ctaid_offsets = unpack(f'{cnt}I', self.info_section.data[offset:offset + size])
            elif code == self.EIATTR['COOP_GROUP_INSTR_OFFSETS']:
                cnt = size // 4
                self.coop_group_instr_offsets = unpack(f'{cnt}I', self.info_section.data[offset:offset + size])
            elif code == self.EIATTR['INT_WARP_WIDE_INSTR_OFFSETS']:
                cnt = size // 4
                self.int_warp_wide_instr_offsets = unpack(f'{cnt}I', self.info_section.data[offset:offset + size])
            elif code == self.EIATTR['INDIRECT_BRANCH_TARGETS']:
                off = offset
                while off < offset + size:
                    instr_addr, z0, z1, c = unpack(f'IHHI', self.info_section.data[off:off + 12])
                    target_addrs = unpack(f'{c}I', self.info_section.data[off + 12:off + 12 + c * 4])
                    self.indirect_branch_targets.append([instr_addr, z0, z1, c, *target_addrs])
                    off += 12 + c * 4
                    if self.indirect_branch_targets[-1][1:3] != [0, 0]:
                        print(f'Warning: unknow INDIRECT_BRANCH_TARGETS: {self.indirect_branch_targets[-1]}')
            elif code == self.EIATTR['CUDA_API_VERSION']:
                self.cuda_api_version = unpack(f'I', self.info_section.data[offset:offset + size])[0]
            elif code == self.EIATTR['SW_WAR']:
                self.sw_war = unpack(f'I', self.info_section.data[offset:offset + size])[0]
            else:
                print(f'Warning: unknow param code: {code.hex()}, size: {size}, '
                      f'data: {self.info_section.data[offset:offset + size].hex()}.')
            offset += size
        self.params.sort(key=lambda d: d['Ordinal'])
        for param in self.params:
            param['Offset'] += self.param_base
        # 猜测frame_size是cuobjdump里面的STACK, 因为不知道怎么编出LOCAL,暂时无法测试。
        # 并且发现 frame_size == min_stack_size, max_stack_size是0
        assert (self.frame_size == self.min_stack_size)
        assert (0 == self.max_stack_size)

    def store_info(self):
        data = b''

        if self.sw_war:
            code = self.EIATTR['SW_WAR']
            size = 4
            data += pack('<2sHI', code, size, self.sw_war)

        if self.cuda_api_version:
            code = self.EIATTR['CUDA_API_VERSION']
            size = 4
            data += pack('<2sHI', code, size, self.cuda_api_version)

        if self.sw2861232_war:
            code = self.EIATTR['SW2861232_WAR']
            size = 0
            data += pack('<2sH', code, size)
        if self.sw2393858_war:
            code = self.EIATTR['SW2393858_WAR']
            size = 0
            data += pack('<2sH', code, size)
        if self.sw1850030_war:
            code = self.EIATTR['SW1850030_WAR']
            size = 0
            data += pack('<2sH', code, size)
        if self.wmma_used:
            code = self.EIATTR['WMMA_USED']
            size = 0
            data += pack('<2sH', code, size)
        if self.param_size:
            code = self.EIATTR['PARAM_CBANK']
            size = 8
            data += pack('<2sHIHH', code, size,
                         self.constant0_section.symbols[0].index, self.param_base, self.param_size)
            code = self.EIATTR['CBANK_PARAM_SIZE']
            data += pack('<2sH', code, self.param_size)
            for param in reversed(self.params):
                code = self.EIATTR['KPARAM_INFO']
                size = 12
                i = 0
                align = param['Align']
                while align:
                    i += 1
                    align = align >> 1
                param_flag = (i - 1) | 0x400 if i else 0
                param_flag |= param['Size'] << 18 | 0x1F000
                data += pack('<2sHIHHI', code, size, 0, param['Ordinal'], param['Offset'] - self.param_base, param_flag)
        if self.maxreg_count:
            code = self.EIATTR['MAXREG_COUNT']
            data += pack('<2sH', code, self.maxreg_count)

        if self.max_threads != [0, 0, 0]:
            code = self.EIATTR['MAX_THREADS']
            size = 12
            data += pack('<2sHIII', code, size, *self.max_threads)

        if self.reqntid != [0, 0, 0]:
            code = self.EIATTR['REQNTID']
            size = 12
            data += pack('<2sHIII', code, size, *self.reqntid)

        if self.ctaidz_used:
            code = self.EIATTR['CTAIDZ_USED']
            size = 0
            data += pack('<2sH', code, size)

        if self.int_warp_wide_instr_offsets:
            code = self.EIATTR['INT_WARP_WIDE_INSTR_OFFSETS']
            size = len(self.int_warp_wide_instr_offsets)
            data += pack(f'<2sH{size}I', code, size * 4, *self.int_warp_wide_instr_offsets)

        if self.coop_group_instr_offsets:
            code = self.EIATTR['COOP_GROUP_INSTR_OFFSETS']
            size = len(self.coop_group_instr_offsets)
            data += pack(f'<2sH{size}I', code, size * 4, *self.coop_group_instr_offsets)

        if self.ctaid_offsets and self.arch < 70:
            code = self.EIATTR['S2RCTAID_INSTR_OFFSETS']
            size = len(self.ctaid_offsets)
            data += pack(f'<2sH{size}I', code, size * 4, *self.ctaid_offsets)

        if self.exit_offsets:
            code = self.EIATTR['EXIT_INSTR_OFFSETS']
            size = len(self.exit_offsets)
            data += pack(f'<2sH{size}I', code, size * 4, *self.exit_offsets)

        if self.indirect_branch_targets:
            code = self.EIATTR['INDIRECT_BRANCH_TARGETS']
            size = 0
            tmp_data = b''
            for item in self.indirect_branch_targets:
                c = len(item) - 4
                tmp_data += pack(f'<IHHI{c}I', *item)
                size += 12 + c * 4
            data += pack('<2sH', code, size)
            data += tmp_data

        if self.crs_stack_size:
            code = self.EIATTR['CRS_STACK_SIZE']
            size = 4
            data += pack('<2sHI', code, size, self.crs_stack_size)

        self.info_section.data = data
        self.info_section.sh_size = len(data)

    def load_asm(self, asm):
        label = ''
        instrs = []
        lines = asm.split('\n')
        for i in range(len(lines)):
            line = lines[i]
            m = re.search(rf'^\s*\.(?P<config>[a-z]\w*)\s*(?P<rest>.*)', line)
            if m:
                config = m.group('config')
                rest = m.group('rest')
                if config == 'stack':
                    self.frame_size = int(rest, base=0)
                    self.min_stack_size = self.frame_size
                elif config == 'sw_war':
                    self.sw_war = int(rest, base=0)
                elif config == 'sw1850030_war':
                    self.sw1850030_war = True
                elif config == 'sw2393858_war':
                    self.sw2393858_war = True
                elif config == 'sw2861232_war':
                    self.sw2861232_war = True
                elif config == 'explicit_caching':
                    self.explicit_caching = True
                elif config == 'crs_stack_size':
                    self.crs_stack_size = int(rest, base=0)
                elif config == 'max_registers':
                    self.maxreg_count = int(rest, base=0)
                elif config == 'max_threads':
                    x, y, z = rest.split(',')
                    x = int(x, base=0)
                    y = int(y, base=0)
                    z = int(z, base=0)
                    self.max_threads = [x, y, z]
                elif config == 'threads':
                    x, y, z = rest.split(',')
                    x = int(x, base=0)
                    y = int(y, base=0)
                    z = int(z, base=0)
                    self.reqntid = [x, y, z]
                elif config == 'shared':
                    self.shared_size = int(rest, base=0)
                elif config == 'param':
                    m = re.search(
                        rf'(?P<ordinal>\d+)\s*,\s*(?P<name>[a-zA-Z_]\w*)\s*,\s*c\[0x0\]\s*\[(?P<offset>{hexx})\]\s*,'
                        rf'\s*(?P<size>\d+|{hexx})',
                        rest)
                    assert m
                    param = {
                        'Ordinal': int(m.group('ordinal')),
                        'Offset': int(m.group('offset'), base=0),
                        'Size': int(m.group('size'), base=0),
                        'Align': 0,
                        'Name': m.group('name') if m.group('name') else ''
                    }
                    self.params.append(param)
                    self.param_base = min(self.param_base, param['Offset'])
                elif config == 'reg':
                    m = re.search(
                        rf'(?P<name>[a-zA-Z_]\w*)\s*,\s*(?P<type>U?[RP])(?P<start>\d+)-?(?P<end>\d+)?',
                        rest)
                    assert m
                    r_name = m.group('name')
                    r_type = m.group('type')
                    r_start = m.group('start')
                    r_end = m.group('end')
                    if r_end:
                        r_start = int(r_start, base=0)
                        r_end = int(r_end, base=0)
                        for n in range(r_end - r_start):
                            self.reg_map[f'{r_type}_{r_name}_{i}'] = f'{r_type}{r_start + i}'
                    else:
                        self.reg_map[f'{r_type}_{r_name}'] = f'{r_type}{r_start}'
            else:
                m = re.search(rf'^{LABEL_RE}', line)
                line_num = len(instrs)
                if m:
                    label = m.group('label')
                    continue
                instr = process_asm_line(line, line_num)
                if instr:
                    instr['label'] = label
                    label = ''
                    instrs.append(instr)

        # kernel size padding
        if self.arch < 70:
            m = 6
        else:
            m = 8
        nop_pad = m - len(instrs) % m if len(instrs) % m else 0
        for i in range(nop_pad):
            line_num = len(instrs)
            instr = process_asm_line('-:--:-:-:Y:0 NOP;', line_num)
            instrs.append(instr)

        for param in self.params:
            self.param_size = max(self.param_size, param['Size'] + param['Offset'] - self.param_base)
        self.instrs = instrs

    def disassemble(self, tmp_file='temp.bin'):
        sass = disassemble_nv(self.binary, self.arch, tmp_file)

        # read sass lines
        instrs = []
        i = 0
        if self.arch < 70:
            while i < len(sass):
                line = sass[i]
                i += 1
                ctrls = process_sass_ctrl_line(line)
                for ctrl in ctrls:
                    line = sass[i]
                    i += 1
                    instr = process_sass_line(line)

                    # 去掉;前的空白
                    instr['rest'] = re.sub(r'\s+;', ';', instr['rest'])
                    # 多个空白变成一个空格
                    instr['rest'] = re.sub(r'[ \t]+', ' ', instr['rest'])

                    instr = {'line_num': len(instrs), 'label': '', 'ctrl': print_ctrl(ctrl), **ctrl, **instr}
                    instrs.append(instr)
        elif self.arch < 90:
            while i < len(sass):
                line = sass[i]
                instr = process_sass_line(line)
                i += 1
                if not instr:
                    continue
                instr = process_sass_code(sass[i], instr)
                i += 1
                if not instr:
                    raise Exception(f'process_sass_code failed: {line}')
                ctrl_binary = (int(instr['code'], base=0) >> 105) & 0x1fffff
                ctrl = decode_ctrl(ctrl_binary)
                # 去掉;前的空白
                instr['rest'] = re.sub(r'\s+;', ';', instr['rest'])
                # 多个空白变成一个空格
                instr['rest'] = re.sub(r'[ \t]+', ' ', instr['rest'])

                instr = {'line_num': len(instrs), 'label': '', 'ctrl': print_ctrl(ctrl), **ctrl, **instr}
                instrs.append(instr)
        else:
            raise Exception(f'Unsupported arch {self.arch}')

        self.instrs = instrs

    def disassemble_ptx(self):
        # 无用指令
        ignore_instrs = ['NOP', 'MEMBAR', 'SSY', 'PBK']
        self.pred_regs = set()
        self.reg_set = set()
        self.ptx_reg_count = 0
        self.ptx_pred_reg_count = 0
        self.reg64_count = 0
        stack_cnt = 0
        instrs = []
        label = ''
        for instr in self.instrs:
            instr['rest'] = re.sub(r'\.reuse', '', instr['rest'])
        for instr in self.instrs:
            op = instr['op']
            rest = instr['rest']
            if instr['line_num'] is None:
                instrs.append(instr)
                continue
            # 忽略无用指令
            if op in ignore_instrs:
                if instr['label']:
                    label = instr['label']
                continue
            if 'R1,' in rest:
                stack_cnt += 1
            # 如果label位于无用指令上，向后调整label位置
            if label:
                instr['label'] = label
                label = ''
            # 处理pred
            if instr['pred']:
                instr['pred'] = f'@{"!" if instr["pred_not"] else ""}%p{instr["pred_reg"]}'
                self.pred_regs.add(int(instr["pred_reg"], base=0))
            grams = grammar_ptx[op] if op in grammar_ptx else []
            gram = None
            captured_dict = None
            for g in grams:
                m = re.search(g['rule'], op + rest)
                if m:
                    gram = g
                    captured_dict = m.groupdict()
                    break
            if not gram:
                #     raise Exception(f'Cannot recognize instruction {op + rest}')
                instr['line_num'] = -instr['line_num']
                instrs.append(instr)
                continue
            else:
                c_instr = instr.copy()
                c_instr['line_num'] = None
                instrs.append(c_instr)
            # 统计寄存器数量
            if 'r0' in captured_dict and captured_dict['r0'] and captured_dict['r0'] != 'RZ':
                r_num = int(captured_dict['r0'][1:])
                self.reg_set.add(r_num)
                if 'type' in captured_dict:
                    c_type = captured_dict['type']
                    if c_type:
                        if '64' in c_type:
                            self.reg_set.add(r_num + 1)
                        if '128' in c_type:
                            self.reg_set.add(r_num + 1)
                            self.reg_set.add(r_num + 2)
                            self.reg_set.add(r_num + 3)

            ptx_func = gram['ptx']
            ptx_func(self, instrs, captured_dict, instr)
            if instr['line_num'] is not None:
                instrs.append(instr)
        if self.pred_regs:
            self.pred_reg_count = max(self.pred_regs) + 1
        self.reg_count = max(self.reg_set) + 1

        # 不使用STACK时，去掉第一条 MOV R1, c[0x0][0x20]
        for instr in instrs:
            if 'ld' in instr['op'].lower() and 'r1' in instr['rest'].lower() and stack_cnt == 1:
                instrs.remove(instr)
                break

        # 去除最后一条死循环
        last_instr = instrs[-1]
        if last_instr['label'] and last_instr['label'] in last_instr['rest']:
            instrs = instrs[:-1]
        self.instrs = instrs

    def assemble(self, test_binary: bytes = b''):
        if self.arch < 70:
            return self.assemble_61(test_binary)
        else:
            return self.assemble_75(test_binary)

    def assemble_61(self, test_binary: bytes = b''):
        # prepare test code
        codes_test = []
        if test_binary:
            codes_test = unpack(f'{len(test_binary) // 8}Q', test_binary)
            codes_test = [codes_test[i:i + 4] for i in range(0, len(codes_test), 4)]

        instrs = [self.instrs[i:i + 3] for i in range(0, len(self.instrs), 3)]
        # instrs = [instrs[i:i + 3] for i in range(0, 12, 3)]
        reg_set = set()
        bar_set = set()
        self.exit_offsets = []
        self.ctaid_offsets = []
        self.ctaidz_used = False
        codes = []
        for i, instr_group in enumerate(instrs):
            ctrl_group = []
            code_group = []
            for instr in instr_group:
                op = instr['op']
                rest = instr['rest']
                grams = grammar_61[op]
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
                ctrl, code = encode_instruction(op, gram, captured_dict, instr, self.arch)
                ctrl_group.append(ctrl)
                code_group.append(code)
                instr['code'] = f'{code:#018x}'
                instr['addr'] = f"{line_num2addr(instr['line_num'], self.arch):04x}"
                instr['reuse'] = (ctrl >> 17) & 0xf
                # 统计寄存器数量
                if 'r0' in captured_dict and captured_dict['r0'] and captured_dict['r0'] != 'RZ':
                    r_num = int(captured_dict['r0'][1:])
                    reg_set.add(r_num)
                    if 'type' in captured_dict:
                        c_type = captured_dict['type']
                        if c_type:
                            if '64' in c_type:
                                reg_set.add(r_num + 1)
                            if '128' in c_type:
                                reg_set.add(r_num + 1)
                                reg_set.add(r_num + 2)
                                reg_set.add(r_num + 3)
                # 统计barrier数量
                if op == 'BAR':
                    bar_id = captured_dict['i8w8']
                    if not bar_id:
                        bar_set.add(15)
                    else:
                        bar_set.add(int(bar_id, base=0))
                # 记录exit指令
                elif op == 'EXIT':
                    self.exit_offsets.append(line_num2addr(instr['line_num'], self.arch))
                # 记录SR_CTAID读取
                elif op == 'S2R':
                    sr_str = captured_dict['sr']
                    if 'SR_CTAID' in sr_str:
                        self.ctaid_offsets.append(line_num2addr(instr['line_num'], self.arch))
                        if 'SR_CTAID.Z' in sr_str:
                            self.ctaidz_used = True
                elif op == 'SHFL':
                    membermask = 32
                    if captured_dict['i34w13']:
                        membermask = int(captured_dict['i34w13'], base=0)
                    if membermask < 32:
                        self.int_warp_wide_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
                    else:
                        self.coop_group_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
                elif op == 'VOTE':
                    self.int_warp_wide_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
                elif op == 'SYNC':  # todo: 将SYNC, BRX BRA指令的地址和目标地址记录到self.indirect_branch_targets
                    # [addr, 0, 0, 1, target_addr]
                    pass

            ctrl = encode_ctrls(*ctrl_group)
            codes.append(ctrl)
            codes += code_group

            if test_binary:
                ctrl_test = codes_test[i][0]
                if ctrl != ctrl_test:
                    print(f'Assemble ctrl failed: /*{i * 0x20:x}*/ {ctrl_test:#018x} != {ctrl:#018x}')
                    for j, (ct, c) in enumerate(zip(decode_ctrls(ctrl_test), decode_ctrls(ctrl))):
                        instr = instr_group[j]['op'] + instr_group[j]['rest']
                        print(f'    /*{i * 0x20 + j * 0x8 + 0x8:x}*/ {instr}')
                        print(f'    ✓ {print_reuse(ct["reuse"])} {print_ctrl(ct)} '
                              f'{ctrl_test >> ((21 * j) & 0x1ffff):#08x}')
                        print(f'    ✕ {print_reuse(c["reuse"])} {print_ctrl(c)} {ctrl((21 * j) & 0x1ffff):#08x}')
                    return b''
                for j, (src, dst) in enumerate(zip(codes_test[i][1:], codes[-3:])):
                    if src != dst:
                        instr = instr_group[j]['op'] + instr_group[j]['rest']
                        print(f'Assemble failed: /*{i * 0x20 + (j + 1) * 0x8:x}*/ {instr}')
                        print(f'    ✓ {src:#018x}')
                        print(f'    ✕ {dst:#018x}')
                        return b''
        if bar_set:
            self.bar_count = max(bar_set) + 1
        self.reg_count = max(reg_set) + 1
        self.binary = pack(f'<{len(codes)}Q', *codes)
        return self.binary

    def assemble_75(self, test_binary: bytes = b''):
        # prepare test code
        codes_test = []
        if test_binary:
            codes_test = unpack(f'{len(test_binary) // 8}Q', test_binary)
            codes_test = [((codes_test[i + 1] << 64) | codes_test[i]) for i in range(0, len(codes_test), 2)]

        instrs = self.instrs
        reg_set = set()
        bar_set = set()
        self.exit_offsets = []
        self.ctaid_offsets = []
        self.ctaidz_used = False
        codes = []
        for i, instr in enumerate(instrs):
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
            ctrl, code = encode_instruction(op, gram, captured_dict, instr, self.arch)
            # 统计寄存器数量
            if 'r16' in captured_dict and captured_dict['r16'] and captured_dict['r16'] != 'RZ':
                r_num = int(captured_dict['r16'][1:])
                reg_set.add(r_num)
                if 'type' in captured_dict:
                    c_type = captured_dict['type']
                    if c_type:
                        if '64' in c_type:
                            reg_set.add(r_num + 1)
                        if '128' in c_type:
                            reg_set.add(r_num + 1)
                            reg_set.add(r_num + 2)
                            reg_set.add(r_num + 3)
            # 统计barrier数量
            if op == 'BAR':
                bar_id = captured_dict['i54w4']
                if not bar_id:
                    bar_set.add(15)
                else:
                    bar_set.add(int(bar_id, base=0))
            # 记录exit指令
            elif op == 'EXIT':
                self.exit_offsets.append(line_num2addr(instr['line_num'], self.arch))
            # 记录SR_CTAID读取
            elif op == 'S2R':
                sr_str = captured_dict['sr']
                if 'SR_CTAID' in sr_str:
                    self.ctaid_offsets.append(line_num2addr(instr['line_num'], self.arch))
                    if 'SR_CTAID.Z' in sr_str:
                        self.ctaidz_used = True
            elif op == 'SHFL':
                membermask = 32
                if 'i40w13' in captured_dict and captured_dict['i40w13']:
                    membermask = int(captured_dict['i40w13'], base=0)
                if membermask < 32:
                    self.int_warp_wide_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
                else:
                    self.coop_group_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
            elif 'VOTE' in op:
                self.int_warp_wide_instr_offsets.append(line_num2addr(instr['line_num'], self.arch))
            elif op == 'SYNC':  # todo: 将SYNC, BRX BRA指令的地址和目标地址记录到self.indirect_branch_targets
                # [addr, 0, 0, 1, target_addr]
                pass
            # todo: 当使用WMMA的时候，设置 EIATTR_WMMA_USED

            code |= ctrl << 105
            codes.append(code)
            instr['code'] = f'{code:#034x}'
            instr['addr'] = f"{line_num2addr(instr['line_num'], self.arch):04x}"
            instr['reuse'] = (ctrl >> 17) & 0xf

            if test_binary:
                code_test = codes_test[i]
                ctrl_test = (code_test >> 105) & 0x1fffff
                # if self.arch >= 80 and 'UR' not in rest:
                #     if op in ['LD', 'LDG']:
                #         code_test &= 0xffffffffffffffffffffffc0ffffffff
                #     elif op in ['ST', 'STG', 'ATOM', 'ATOMG']:
                #         code_test &= 0xffffffffffffffc0ffffffffffffffff
                if code != code_test:
                    if ctrl != ctrl_test:
                        c = decode_ctrl(ctrl)
                        ct = decode_ctrl(ctrl_test)
                        print(f'Assemble ctrl failed: /*{i * 0x10:x}*/ {ctrl_test:#08x} != {ctrl:#08x}')
                        print(f'    ✓ {print_reuse(ct["reuse"])} {print_ctrl(ct)} {ctrl_test:#08x}')
                        print(f'    ✕ {print_reuse(c["reuse"])} {print_ctrl(c)} {ctrl:#08x}')
                    print(f'Assemble failed: /*{i * 0x10:x}*/ {print_instr(instr)}')
                    print(f'    ✓ {code_test:#034x}')
                    print(f'    ✕ {code:#034x}')
                    return b''
        if bar_set:
            self.bar_count = max(bar_set) + 1
        self.reg_count = max(reg_set) + 3
        codes64 = []
        for code in codes:
            codes64.append(code & 0xffffffffffffffff)
            codes64.append(code >> 64)
        self.binary = pack(f'<{len(codes64)}Q', *codes64)
        return self.binary

    def check_reg_bank(self):
        reuse_history = [[-1, -1], [-1, -1], [-1, -1], [-1, -1]]
        for i, instr in enumerate(self.instrs):
            op = instr['op']
            rest = instr['rest']
            grams = grammar_61[op]
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
            if 'r39s20' in captured_dict:
                captured_dict['r20'] = captured_dict['r39s20']
                captured_dict['r39s20'] = ''
            banks = [[], [], [], []]
            for reg_, reuse in {'r8': 'reuse1', 'r20': 'reuse2', 'r39': 'reuse3'}.items():
                if reg_ not in captured_dict:
                    continue
                r = captured_dict[reg_]
                if reuse not in captured_dict:
                    u = ''
                else:
                    u = captured_dict[reuse]
                if not r or r == 'RZ':
                    continue
                r_n = int(r[1:])
                u_n = int(reuse[-1:])
                bank = r_n & 3
                if r_n in reuse_history[u_n][-2:]:
                    continue
                banks[bank].append(r)
                if u:
                    reuse_history[u_n].append(r_n)
                yield_ = instr['ctrl'][-3]
                if yield_ == 'Y':
                    reuse_history = [[-1, -1], [-1, -1], [-1, -1], [-1, -1]]
            if any([len(x) > 1 for x in banks]):
                print(f'Back conflict: {op + rest}')
                for j, bank in enumerate(banks):
                    if len(bank) > 1:
                        print(f'    bank{j}: {", ".join(bank)}')

    def sort_banks(self):
        bank_map_r = {0: 0}
        bank_map_ur = {0: 0}

        def replace_reg(x: re.Match):
            ur = x.group('UR')
            if ur:
                bank_map = bank_map_ur
            else:
                bank_map = bank_map_r
            reg_num = int(x.group('num'), base=0)
            bank = reg_num & 3
            bank_slot = reg_num >> 2
            if bank_slot not in bank_map:
                bank_map[bank_slot] = max(bank_map.values()) + 1
            new_reg_num = (bank_map[bank_slot] << 2) + bank
            return f'{ur}R{new_reg_num}'

        for instr in self.instrs:
            rest = instr['rest']
            instr['rest'] = re.sub(rf'(?P<UR>U?)R(?P<num>\d+)', replace_reg, rest)

    def schedule(self):
        if self.arch < 70:
            self.instrs = schedule_61(self.instrs)
        else:
            self.instrs = schedule_75(self.instrs)

        if not self.rel_map:
            for rel in self.rels:
                line_num = addr2line_num(rel.r_offset, self.arch)
                self.rel_map[line_num] = rel

        # update line_num and global Relocation
        for i, instr in enumerate(self.instrs):
            line_num = instr['line_num']
            if line_num in self.rel_map:
                self.rel_map[line_num].r_offset = line_num2addr(i, self.arch)
            instr['line_num'] = i

    def gen_sections(self):
        # .text section
        section = Section()
        section.name = b'.text.' + self.name
        if self.arch < 70:
            section.sh_addralign = 32
        else:
            section.sh_addralign = 128
        section.sh_flags = Section.SHF_VAL['X'] | Section.SHF_VAL['A'] | (self.bar_count << 20)
        section.sh_info = (self.reg_count << 24)
        section.sh_link = 3
        section.data = self.binary
        section.sh_size = len(section.data)
        section.sh_type = Section.SHT_VAL['PROGBITS']
        self.section = section

        # shared_section
        if self.shared_size:
            shared_section = Section()
            shared_section.name = b'.nv.shared.' + self.name
            shared_section.sh_addralign = 8
            shared_section.sh_flags = Section.SHF_VAL['W'] | Section.SHF_VAL['A']
            shared_section.sh_size = self.shared_size
            shared_section.sh_type = Section.SHT_VAL['NOBITS']
            self.shared_section = shared_section

        # constant0_section
        constant0_section = Section()
        constant0_section.name = b'.nv.constant0.' + self.name
        constant0_section.sh_addralign = 4
        constant0_section.sh_flags = Section.SHF_VAL['A']
        constant0_section.sh_type = Section.SHT_VAL['PROGBITS']
        if self.arch < 70:
            size = 320 + self.param_size
        else:
            size = 320 + self.param_size + 32
        constant0_section.sh_size = size
        constant0_section.data = b'\0' * size
        self.constant0_section = constant0_section

        # constant2_section
        if self.constant2:
            constant2_section = Section()
            constant2_section.name = b'.nv.constant2.' + self.name
            constant2_section.sh_addralign = self.constant2.align
            constant2_section.sh_flags = Section.SHF_VAL['A']
            constant2_section.sh_type = Section.SHT_VAL['PROGBITS']
            constant2_section.sh_size = self.constant2.size
            constant2_section.data = self.constant2.binary
            self.constant2_section = constant2_section

        # rel_section
        if self.rels:
            rel_section = Section()
            rel_section.name = b'.rel.text.' + self.name
            rel_section.sh_addralign = 8
            rel_section.sh_entsize = 16
            rel_section.sh_link = 3
            rel_section.sh_type = Section.SHT_VAL['REL']
            self.rel_section = rel_section

        # info_section
        info_section = Section()
        info_section.name = b'.nv.info.' + self.name
        info_section.sh_addralign = 4
        info_section.sh_link = 3
        info_section.sh_type = Section.SHT_VAL['CUDA_INFO']
        self.info_section = info_section

    def gen_rels(self, symbol_dict):
        for rel in reversed(self.rels):
            rel.sym = symbol_dict[rel.sym_name].index
            rel.r_info = rel.type | (rel.sym << 32)
            self.rel_section.data += rel.pack_entry()
        if self.rel_section:
            self.rel_section.sh_size = len(self.rel_section.data)
