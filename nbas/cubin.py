from .kernel import *

out_ = ''


class Cubin(ELF):
    EIATTR = {
        'FRAME_SIZE': b'\x04\x11',
        'MIN_STACK_SIZE': b'\x04\x12',
        'MAX_STACK_SIZE': b'\x04\x23',
        'REGCOUNT': b'\x04\x2f',
    }

    def __init__(self, iterable=(), **kwargs):
        super().__init__(iterable, **kwargs)
        self.kernel_dict = {}
        self.constant_dict = {}
        self.constant_map = {}
        self.global_dict = {}
        self.global_init_dict = {}

        self.info_section = None
        self.constant_section = None
        self.global_section = None
        self.global_init_section = None

        self.arch = 61

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        msg = super().__repr__()
        msg += f', kernels:{[n.decode() for n in self.kernel_dict.keys()]}'
        return msg

    def load(self, path, global_only=False):
        super().load(path)

        self.arch = self.header.arch
        # For the Global functions, extract kernel meta data
        for symbol in self.symbols:
            section = self.sections[symbol.st_shndx]

            # Look for symbols tagged FUNC
            if symbol.type == Symbol.STT_VAL['FUNC'] and (symbol.bind == Symbol.STB_VAL['GLOBAL'] or (not global_only)):
                # create kernel dict
                kernel = Kernel()
                kernel.section = section
                kernel.binary = kernel.section.data
                kernel.name = symbol.name
                kernel.arch = self.arch
                self.kernel_dict[symbol.name] = kernel

                # Extract local/global/weak binding info
                kernel.linkage = symbol.bind

                # Extract the max barrier resource identifier used and add 1. Should be 0-16.
                # If a register is used as a barrier resource id, then this value is the max of 16.
                kernel.bar_count = (kernel.section.sh_flags & 0x01f00000) >> 20

                # Extract the number of allocated registers for this kernel.
                kernel.reg_count = (kernel.section.sh_info & 0xff000000) >> 24

                # Extract the size of shared memory this kernel uses.
                shared_sec_name = b'.nv.shared.' + symbol.name
                if shared_sec_name in self.section_dict:
                    kernel.shared_section = self.section_dict[shared_sec_name]
                    kernel.shared_size = kernel.shared_section.sh_size

                # Attach constant0 section
                constant0_sec_name = b'.nv.constant0.' + symbol.name
                if constant0_sec_name in self.section_dict:
                    kernel.constant0_section = self.section_dict[constant0_sec_name]
                    kernel.constant0_size = kernel.constant0_section.sh_size

                # Attach constant2 section
                constant2_sec_name = b'.nv.constant2.' + symbol.name
                if constant2_sec_name in self.section_dict:
                    kernel.constant2_section = self.section_dict[constant2_sec_name]
                    # kernel.constant2 = kernel.constant2_section.sh_size
                    kernel.constant2 = Data(name=kernel.name,
                                            type='constant2',
                                            align=kernel.constant2_section.sh_addralign,
                                            offset=0,
                                            size=kernel.constant2_section.sh_size,
                                            binary=kernel.constant2_section.data)

                # Attach relocation section
                rel_sec_name = b'.rel.text.' + symbol.name
                if rel_sec_name in self.section_dict:
                    kernel.rel_section = self.section_dict[rel_sec_name]
                    kernel.rels = []
                    offset = 0
                    while offset < kernel.rel_section.sh_size:
                        rel = Relocation()
                        rel.unpack_binary(kernel.rel_section.data[offset:offset + kernel.rel_section.sh_entsize])
                        rel.sym_name = self.symbols[rel.sym].name
                        kernel.rels.append(rel)
                        offset += kernel.rel_section.sh_entsize

                # Attach relocation add section
                rela_sec_name = b'.rela.text.' + symbol.name
                if rela_sec_name in self.section_dict:
                    kernel.rela_section = self.section_dict[rela_sec_name]
                    kernel.relas = []
                    offset = 0
                    while offset < kernel.rela_section.sh_size:
                        rela = RelocationAdd()
                        rela.unpack_binary(kernel.rela_section.data[offset:offset + kernel.rela_section.sh_entsize])
                        rela.sym_name = self.symbols[rela.sym].name
                        kernel.relas.append(rela)
                        offset += kernel.rela_section.sh_entsize

                # Extract the kernel meta data.
                info_sec_name = b'.nv.info.' + symbol.name
                if info_sec_name in self.section_dict:
                    kernel.load_info(self.section_dict[info_sec_name])

        # 解析 .nv.info 其中包含每个kernel的FRAME_SIZE, MIN_STACK_SIZE, MAX_STACK_SIZE, REGCOUNT
        info_section: Section = self.section_dict[b'.nv.info']
        self.info_section = info_section
        offset = 0
        while offset < info_section.sh_size:
            code, size = unpack('2sH', info_section.data[offset:offset + 4])
            offset += 4
            if code == self.EIATTR['FRAME_SIZE']:
                kernel_idx, frame_size = unpack('II', info_section.data[offset:offset + size])
                kernel_name = self.symbols[kernel_idx].name
                if kernel_name in self.kernel_dict:
                    self.kernel_dict[kernel_name].frame_size = frame_size
            elif code == self.EIATTR['MIN_STACK_SIZE']:
                kernel_idx, min_stack_size = unpack('II', info_section.data[offset:offset + size])
                kernel_name = self.symbols[kernel_idx].name
                if kernel_name in self.kernel_dict:
                    self.kernel_dict[kernel_name].min_stack_size = min_stack_size
            elif code == self.EIATTR['MAX_STACK_SIZE']:
                kernel_idx, max_stack_size = unpack('II', info_section.data[offset:offset + size])
                kernel_name = self.symbols[kernel_idx].name
                if kernel_name in self.kernel_dict:
                    self.kernel_dict[kernel_name].max_stack_size = max_stack_size
            elif code == self.EIATTR['REGCOUNT']:
                kernel_idx, reg_count = unpack('II', info_section.data[offset:offset + size])
                # 使用 sh_info 获取 reg_count，这里也可以
                if self.kernel_dict[self.symbols[kernel_idx].name].reg_count != reg_count:
                    print(f'Warning: reg_count not match: '
                          f'{self.kernel_dict[self.symbols[kernel_idx].name].reg_count} != {reg_count}')
            else:
                print(f'Warning: unknow nv.info '
                      f'code: {code.hex()}, size: {size}, data: {info_section.data[offset:offset + size].hex()}.')
            offset += size

        # 解析 .nv.constant3
        if b'.nv.constant3' in self.section_dict:
            constant_section: Section = self.section_dict[b'.nv.constant3']
            self.constant_section = constant_section
            self.constant_dict = self.load_data(constant_section, 'constant')

        # 解析 .nv.global
        if b'.nv.global' in self.section_dict:
            global_section_name = b'.nv.global'
            global_section: Section = self.section_dict[global_section_name]
            self.global_section = global_section
            self.global_dict = self.load_data(global_section, 'global')
        if b'.nv.global.init' in self.section_dict:
            global_init_section_name = b'.nv.global.init'
            global_init_section: Section = self.section_dict[global_init_section_name]
            self.global_init_section = global_init_section
            self.global_init_dict = self.load_data(global_init_section, 'global')

    @staticmethod
    def load_data(section, type_):
        data_dict = {}
        for symbol in section.symbols:
            if symbol.type == Symbol.STT_VAL['OBJECT']:
                data = Data(name=symbol.name,
                            type=type_,
                            align=section.sh_addralign,
                            offset=symbol.st_value,
                            size=symbol.st_size,
                            binary=section.data[
                                   symbol.st_value:symbol.st_value + symbol.st_size])
                data_dict[symbol.name] = data
        return data_dict

    def map_constant3(self, kernel):
        if not self.constant_map:
            for c in self.constant_dict.values():
                begin = c.offset
                end = begin + c.size
                name = c.name
                for i in range(begin, end):
                    self.constant_map[i] = {'Name': name, 'Offset': i - begin}

        def map_const(x):
            offset = int(x.group('offset'), 0)
            name_ = self.constant_map[offset]['Name']
            offset = self.constant_map[offset]['Offset']
            kernel.consts.add(name_)
            return f'c[{name_.decode()}+{offset}]'

        for instr in kernel.instrs:
            instr['rest'] = re.sub(rf'(?P<c>c\[0x3\]\s*\[(?P<offset>{hexx})\])', map_const, instr['rest'])
            if re.search(ldc, instr['rest']):
                kernel.consts.add('ALL_CONST3')

    def unmap_constant3(self, kernel):
        def unmap_const(x):
            name = x.group('name')
            if not x.group('offset'):
                return f'c[{name}]'
            offset = int(x.group('offset'), 0)
            name_b = name.encode()
            if name_b in self.constant_dict:
                data = self.constant_dict[name_b]
                offset += data.offset
                return f'c[0x3][{offset:#0x}]'
            else:
                return f'c[{name}+{offset}]'

        for instr in kernel.instrs:
            instr['rest'] = re.sub(rf'{CONST_NAME_RE}', unmap_const, instr['rest'])

    def load_asm_header(self, asm):
        m = re.search(ARCH_RE, asm)
        assert m
        self.arch = int(m.group('arch'))
        m = re.search(COMPUTE_RE, asm)
        if m:
            virtual_arch = int(m.group('compute'))
        else:
            virtual_arch = self.arch
        if self.arch <= 75:
            e_version = 102
        else:
            e_version = 111
        self.header = Header(arch=self.arch, virtual_arch=virtual_arch, e_version=e_version)

    def load_asm_data(self, asm):
        # load global, const3, const2
        d_type = {
            'byte': f'B',
            'short': f'H',
            'word': f'I',
            'quad': f'Q',
        }
        global_offset = 0
        global_init_offset = 0
        constant_offset = 0
        match_list = re.finditer(DATA_RE, asm)
        for m in match_list:
            captured_dict = m.groupdict()
            data = Data(
                name=captured_dict['name'].encode(),
                type=captured_dict['type'],
                align=int(captured_dict['align'])
            )
            rows = re.finditer(DATA_ROW_RE, captured_dict['data'])
            for row in rows:
                row = row.groupdict()
                if row['type'] == 'zero':
                    data.size = int(row['data'], base=0)
                    data.binary = b''
                    break
                d = [int(x, base=0) for x in row['data'].strip(',').split(',')]
                binary = pack(f"<{len(d)}{d_type[row['type']]}", *d)
                data.size += len(binary)
                data.binary += binary
            if data.type == 'global':
                if data.binary == b'':
                    data.offset = align_offset(global_offset, min(data.align, data.size))
                    global_offset = data.offset + data.size
                    self.global_dict[data.name] = data
                else:
                    data.offset = align_offset(global_init_offset, min(data.align, data.size))
                    global_init_offset = data.offset + data.size
                    self.global_init_dict[data.name] = data
            elif data.type == 'constant':
                data.offset = align_offset(constant_offset, min(data.align, data.size))
                constant_offset = data.offset + data.size
                self.constant_dict[data.name] = data
            else:
                if data.name in self.kernel_dict:
                    kernel = self.kernel_dict[data.name]
                else:
                    kernel = Kernel()
                    self.kernel_dict[data.name] = kernel
                    kernel.name = data.name
                    kernel.arch = self.arch
                kernel.constant2 = data

        # 反向排序global，与原始cubin一致
        global_init_offset = 0
        for data in reversed(self.global_init_dict.values()):
            data.offset = align_offset(global_init_offset, min(data.align, data.size))
            global_init_offset = data.offset + data.size

    def load_asm_kernels(self, asm):
        # load kernel
        match_list = re.finditer(KERNEL_RE, asm)
        for m in match_list:
            captured_dict = m.groupdict()
            kernel_name = captured_dict['name'].encode()
            if kernel_name in self.kernel_dict:
                kernel = self.kernel_dict[kernel_name]
            else:
                kernel = Kernel()
                self.kernel_dict[kernel_name] = kernel
                kernel.name = kernel_name
                kernel.arch = self.arch
            kernel.load_asm(captured_dict['data'])

    def add_sh_str(self, name):
        offset = len(self.shstrtab.data)
        self.shstrtab.data += name + b'\0'
        self.shstrtab.sh_size = len(self.shstrtab.data)
        return offset

    def add_sym_str(self, name):
        offset = len(self.strtab.data)
        self.strtab.data += name + b'\0'
        self.strtab.sh_size = len(self.strtab.data)
        return offset

    def gen_sections(self):
        self.sections = []

        # null section
        null_section = Section()
        self.sections.append(null_section)

        # shstrtab
        shstrtab = Section()
        self.shstrtab = shstrtab
        shstrtab.data = b'\0'
        shstrtab.name = b'.shstrtab'
        shstrtab.sh_addralign = 1
        shstrtab.sh_name = self.add_sh_str(shstrtab.name)
        shstrtab.sh_type = Section.SHT_VAL['STRTAB']
        self.sections.append(shstrtab)

        # strtab, symtab
        strtab = Section()
        self.strtab = strtab
        strtab.data = b'\0'
        strtab.name = b'.strtab'
        strtab.sh_addralign = 1
        strtab.sh_name = self.add_sh_str(strtab.name)
        strtab.sh_type = Section.SHT_VAL['STRTAB']
        self.sections.append(strtab)

        # symtab
        symtab = Section()
        self.symtab = symtab
        symtab.name = b'.symtab'
        symtab.sh_addralign = 8
        symtab.sh_entsize = 24
        symtab.sh_link = 2
        symtab.sh_name = self.add_sh_str(symtab.name)
        symtab.sh_type = Section.SHT_VAL['SYMTAB']
        self.sections.append(symtab)

        # nv info
        section = Section()
        section.name = b'.nv.info'
        section.sh_name = self.add_sh_str(section.name)
        section.sh_addralign = 4
        section.sh_link = 3
        section.sh_type = Section.SHT_VAL['CUDA_INFO']
        self.info_section = section
        self.sections.append(section)

        # const3
        if self.constant_dict:
            section = Section()
            section.name = b'.nv.constant3'
            section.sh_flags = Section.SHF_VAL['A']
            section.sh_name = self.add_sh_str(section.name)
            section.sh_type = Section.SHT_VAL['PROGBITS']
            self.constant_section = section

        # global
        if self.global_dict:
            section = Section()
            section.name = b'.nv.global'
            section.sh_flags = Section.SHF_VAL['A'] | Section.SHF_VAL['W']
            section.sh_name = self.add_sh_str(section.name)
            section.sh_type = Section.SHT_VAL['NOBITS']
            self.global_section = section
        if self.global_init_dict:
            section = Section()
            section.name = b'.nv.global.init'
            section.sh_flags = Section.SHF_VAL['A'] | Section.SHF_VAL['W']
            section.sh_name = self.add_sh_str(section.name)
            section.sh_type = Section.SHT_VAL['PROGBITS']
            self.global_init_section = section

        # kernel sections
        for kernel in self.kernel_dict.values():
            kernel.gen_sections()
            kernel.section.sh_name = self.add_sh_str(kernel.section.name)
            if kernel.shared_section:
                kernel.shared_section.sh_name = self.add_sh_str(kernel.shared_section.name)
            kernel.constant0_section.sh_name = self.add_sh_str(kernel.constant0_section.name)
            if kernel.constant2_section:
                kernel.constant2_section.sh_name = self.add_sh_str(kernel.constant2_section.name)
            kernel.info_section.sh_name = self.add_sh_str(kernel.info_section.name)
            if kernel.rel_section:
                kernel.rel_section.sh_name = self.add_sh_str(kernel.rel_section.name)
            if kernel.rela_section:
                kernel.rela_section.sh_name = self.add_sh_str(kernel.rela_section.name)

        for kernel in self.kernel_dict.values():
            self.sections.append(kernel.info_section)

        for kernel in self.kernel_dict.values():
            if kernel.rel_section:
                self.sections.append(kernel.rel_section)
            if kernel.rela_section:
                self.sections.append(kernel.rela_section)

        if self.constant_section:
            self.sections.append(self.constant_section)

        for kernel in self.kernel_dict.values():
            if kernel.constant2_section:
                self.sections.append(kernel.constant2_section)
            self.sections.append(kernel.constant0_section)

        for kernel in self.kernel_dict.values():
            self.sections.append(kernel.section)

        if self.global_init_section:
            self.sections.append(self.global_init_section)

        for kernel in self.kernel_dict.values():
            if kernel.shared_section:
                self.sections.append(kernel.shared_section)

        if self.global_section:
            self.sections.append(self.global_section)

        for i, section in enumerate(self.sections):
            section.index = i
            self.section_dict[section.name] = section

        # update sh_info for .*.{kernel} sections
        for kernel in self.kernel_dict.values():
            if kernel.shared_section:
                kernel.shared_section.sh_info = kernel.section.index
            kernel.constant0_section.sh_info = kernel.section.index
            if kernel.constant2_section:
                kernel.constant2_section.sh_info = kernel.section.index
            kernel.info_section.sh_info = kernel.section.index
            if kernel.rel_section:
                kernel.rel_section.sh_info = kernel.section.index
            if kernel.rela_section:
                kernel.rela_section.sh_info = kernel.section.index

    def gen_symbols(self):
        self.symbols = []

        # first null symbol
        symbol = Symbol()
        self.symbols.append(symbol)

        # sections
        for section in self.sections:
            if section.sh_type == Section.SHT_VAL['NOBITS'] or section.sh_type == Section.SHT_VAL['PROGBITS']:
                symbol = Symbol(type=Symbol.STT_VAL['SECTION'],
                                name=section.name,
                                st_value=0,
                                st_size=0,
                                st_shndx=section.index,
                                st_other=Symbol.STV_VAL['DEFAULT'])
                symbol.st_name = self.add_sym_str(symbol.name)
                symbol.st_info = symbol.type
                section.symbols.append(symbol)
                self.symbols.append(symbol)

        # const3
        section = self.constant_section
        for data in self.constant_dict.values():
            section.sh_addralign = max(section.sh_addralign, data.align)
            symbol = Symbol(type=Symbol.STT_VAL['OBJECT'],
                            name=data.name,
                            st_value=data.offset,
                            st_size=data.size,
                            st_shndx=section.index,
                            st_other=Symbol.STV_VAL['DEFAULT'])
            symbol.st_name = self.add_sym_str(symbol.name)
            symbol.st_info = symbol.type
            section.symbols.append(symbol)
            self.symbols.append(symbol)
            if data.offset > section.sh_size:
                section.data += b'\0' * (data.offset - section.sh_size)
            section.data += data.binary
            section.sh_size = len(section.data)

        # global init
        section = self.global_init_section
        for data in reversed(self.global_init_dict.values()):
            section.sh_addralign = max(section.sh_addralign, data.align)
            symbol = Symbol(type=Symbol.STT_VAL['OBJECT'],
                            name=data.name,
                            st_value=data.offset,
                            st_size=data.size,
                            st_shndx=section.index,
                            st_other=Symbol.STV_VAL['DEFAULT'])
            symbol.st_name = self.add_sym_str(symbol.name)
            symbol.st_info = symbol.type
            section.symbols.append(symbol)
            self.symbols.append(symbol)
            if data.offset > section.sh_size:
                section.data += b'\0' * (data.offset - section.sh_size)
            section.data += data.binary
            section.sh_size = len(section.data)

        # global
        section = self.global_section
        for data in self.global_dict.values():
            section.sh_addralign = max(section.sh_addralign, data.align)
            symbol = Symbol(type=Symbol.STT_VAL['OBJECT'],
                            name=data.name,
                            st_value=data.offset,
                            st_size=data.size,
                            st_shndx=section.index,
                            st_other=Symbol.STV_VAL['DEFAULT'])
            symbol.st_name = self.add_sym_str(symbol.name)
            symbol.st_info = symbol.type
            section.symbols.append(symbol)
            self.symbols.append(symbol)
            section.sh_size = max(section.sh_size, data.offset + data.size)

        self.symtab.sh_info = len(self.symbols) - 1
        for kernel in self.kernel_dict.values():
            section = kernel.section
            kernel.symbol_idx = len(self.symbols)
            section.sh_info |= kernel.symbol_idx
            symbol = Symbol(type=Symbol.STT_VAL['FUNC'],
                            name=kernel.name,
                            st_value=0,
                            st_size=section.sh_size,
                            st_shndx=section.index,
                            st_other=Symbol.STV_VAL['CUDA_FUNC'],
                            bind=Symbol.STB_VAL['GLOBAL'])
            symbol.st_name = self.add_sym_str(symbol.name)
            symbol.st_info = symbol.type | (symbol.bind << 4)
            section.symbols.append(symbol)
            self.symbols.append(symbol)

        for i, symbol in enumerate(self.symbols):
            self.symtab.data += symbol.pack_entry()
            symbol.index = i
            self.symbol_dict[symbol.name] = symbol
        self.symtab.sh_size = len(self.symtab.data)

    def gen_rels(self):
        for kernel in self.kernel_dict.values():
            kernel.gen_rels(self.symbol_dict)

    def gen_nv_info(self):
        data = b''
        for kernel in self.kernel_dict.values():
            kernel.store_info()
            size = 8
            code = self.EIATTR['REGCOUNT']
            data += pack('<2sHII', code, size, kernel.symbol_idx, kernel.reg_count)
            code = self.EIATTR['MAX_STACK_SIZE']
            data += pack('<2sHII', code, size, kernel.symbol_idx, kernel.max_stack_size)
            code = self.EIATTR['MIN_STACK_SIZE']
            data += pack('<2sHII', code, size, kernel.symbol_idx, kernel.min_stack_size)
            code = self.EIATTR['FRAME_SIZE']
            data += pack('<2sHII', code, size, kernel.symbol_idx, kernel.frame_size)
        self.info_section.data = data
        self.info_section.sh_size = len(data)

    def gen_program(self):
        offset = 64  # elf header size
        for section in self.sections[1:]:
            section.sh_offset = align_offset(offset, section.sh_addralign)
            offset = section.sh_offset + section.sh_size

        p1_begin = 0
        p1_end = 0
        p2_end = 0
        p2_msize = 0
        for section in self.sections:
            if p1_begin == 0 and section.name.startswith(b'.nv.constant'):
                p1_begin = section.sh_offset
            if section.name.startswith(b'.text.'):
                p1_end = section.sh_offset + section.sh_size
            if section.sh_type == Section.SHT_VAL['PROGBITS']:
                p2_end = section.sh_offset + section.sh_size
            if section.sh_type == Section.SHT_VAL['NOBITS']:
                p2_msize = max(p2_msize, section.sh_size)

        p2_begin = p1_end
        p2_end = align_offset(p2_end, 8)
        p2_fsize = p2_end - p2_begin
        p2_msize += p2_fsize

        # Section Header size
        self.header.e_shoff = p2_end
        self.header.e_shnum = len(self.sections)
        sh_size = self.header.e_shnum * self.header.e_shentsize

        # PHDR
        phdr = Program()
        phdr.p_filesz = 168
        phdr.p_memsz = 168
        phdr.p_flags = Program.PF_VAL['R'] | Program.PF_VAL['X']
        phdr.p_offset = p2_end + sh_size
        phdr.p_type = Program.SHT_VAL['PHDR']
        self.programs.append(phdr)

        self.header.e_phnum = 3
        self.header.e_phoff = phdr.p_offset

        # Program 1
        p1 = Program()
        p1.p_filesz = p1_end - p1_begin
        p1.p_memsz = p1_end - p1_begin
        p1.p_flags = Program.PF_VAL['R'] | Program.PF_VAL['X']
        p1.p_offset = p1_begin
        p1.p_type = Program.SHT_VAL['LOAD']
        self.programs.append(p1)

        # Program 2
        if p2_fsize == p2_msize == 0:
            p2_begin = 0
        p2 = Program()
        p2.p_filesz = p2_fsize
        p2.p_memsz = p2_msize
        p2.p_flags = Program.PF_VAL['R'] | Program.PF_VAL['W']
        p2.p_offset = p2_begin
        p2.p_type = Program.SHT_VAL['LOAD']
        self.programs.append(p2)

    def load_asm(self, asm_path, define_dict):
        with open(asm_path, 'r') as f:
            asm = f.read()

        while re.search(INCLUDE_RE, asm) or re.search(PYTHON_RE, asm):
            # include nested files
            asm = process_include(asm, asm_path, define_dict)

            # run embedded python code
            asm = process_python_code(asm, define_dict)

        # strip space
        asm = strip_space(asm)

        # read header
        self.load_asm_header(asm)

        # read global, const3, const2
        self.load_asm_data(asm)

        # read kernels
        self.load_asm_kernels(asm)

    # def print_ptx(self):
    #     pass
    #
    # def merge(self, cubin):
    #     pass
