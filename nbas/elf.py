from struct import unpack, pack


def align_offset(offset, align):
    if align and offset % align != 0:
        offset += align - (offset % align)
    return offset


class Header:
    ELFMAG = b'\x7fELF'
    ELFCLASS64 = 2
    ELFDATA2LSB = 1
    EV_CURRENT = 1
    ELFOSABI_CUDA = 0x33  # 51
    CUDA_ABIVERSION = 7
    ET_EXEC = 2
    EM_CUDA = 0xbe  # 190

    # e_flags定义
    EF_CUDA_SM = 0xFF
    EF_CUDA_TEXMODE_UNIFIED = 0x100
    EF_CUDA_TEXMODE_INDEPENDENT = 0x200
    EF_CUDA_64BIT_ADDRESS = 0x400
    EF_CUDA_SW_1729687 = 0x800
    EF_CUDA_SW_1729687_v2 = 0x1000
    EF_CUDA_VIRTUAL_SM = 0xFF0000

    def __init__(self, iterable=(), **kwargs):
        # ELF文件头 按顺序
        # ELF file magic number: 0x7f E L F
        self.ei_mag = self.ELFMAG  # uint8_t[4]
        # architecture: 32-bit | 64-bit
        self.ei_class = self.ELFCLASS64  # uint8_t
        # data encoding: little-endian
        self.ei_data = self.ELFDATA2LSB  # uint8_t
        # version 1
        self.ei_version = self.EV_CURRENT  # uint8_t
        # ABI: CUDA 0x33
        self.ei_osabi = self.ELFOSABI_CUDA  # uint8_t
        # ABIVERSION: 7
        self.ei_abiversion = self.CUDA_ABIVERSION  # uint8_t
        # zero padding
        self.ei_pad = b'\0' * 7  # uint8_t[7]
        # EXEC
        self.e_type = self.ET_EXEC  # uint16_t
        # CUDA
        self.e_machine = self.EM_CUDA  # uint16_t
        # CUDA version
        self.e_version = 102  # uint32_t
        # virtual address to entry point, Always 0 for cubin
        self.e_entry = 0  # Elf32: uint32_t | Elf64: uint64_t
        # the program header table's file offset in bytes
        self.e_phoff = 0  # Elf32: uint32_t | Elf64: uint64_t
        # the section header table's file offset in bytes
        self.e_shoff = 0  # Elf32: uint32_t | Elf64: uint64_t
        # flags&0xFF 对应nvcc的code=sm_{xx} 50 61 70 75 等等
        # flags&0xFF0000 对应nvcc的arch=compute_{xx} 50 61 70 75 等等
        # flags&0x1F00 5个标志位，见前面EF_CUDA_*定义
        # 剩下的11位好像未使用
        self.e_flags = 0x0500  # uint32_t
        # ELF Header size: Elf64: 64 Bytes | Elf32: 52 Bytes
        self.e_ehsize = 64  # uint16_t
        # program header's size in bytes
        self.e_phentsize = 56  # uint16_t
        # number of entries in the program header table
        self.e_phnum = 0  # uint16_t
        # sections header's size in bytes
        self.e_shentsize = 64  # uint16_t
        # number of entries in the section header table
        self.e_shnum = 0  # uint16_t
        # section name string table index
        self.e_shstrndx = 1  # uint16_t

        # 其他变量
        self.arch = 61
        self.virtual_arch = 61
        self.address_size = 64

        self.__dict__.update(iterable, **kwargs)

        self.e_flags |= self.arch + (self.virtual_arch << 16)

    def __repr__(self):
        cuda_version = f'{self.e_version // 10}.{self.e_version % 10}'
        ph_end = self.e_phoff + self.e_phnum * self.e_phentsize
        sh_end = self.e_shoff + self.e_shnum * self.e_shentsize
        msg = f'CUDA:{cuda_version}, compute:{self.virtual_arch}, sm:{self.arch}, ' \
              f'Flags:{(self.e_flags & 0x1F00) >> 8:05b}, ' \
              f'ProgramHeader:{self.e_phnum}_[{self.e_phoff:#0x}-{ph_end:#0x}]_{self.e_phentsize}, ' \
              f'SectionHeader:{self.e_shnum}_[{self.e_shoff:#0x}-{sh_end:#0x}]_{self.e_shentsize}'
        return msg

    def __eq__(self, other):
        self_dict = self.__dict__.copy()
        other_dict = other.__dict__.copy()
        self_dict['e_phoff'] = 0
        self_dict['e_shoff'] = 0
        other_dict['e_phoff'] = 0
        other_dict['e_shoff'] = 0
        return self_dict == other_dict

    def print(self):
        cuda_version = f'{self.e_version // 10}.{self.e_version % 10}'
        asm = f'# CUDA: {cuda_version}\n'
        asm += f'# arch=compute_{self.virtual_arch}, code=sm_{self.arch}\n'
        if self.e_flags & self.EF_CUDA_TEXMODE_UNIFIED:
            asm += f'# EF_CUDA_TEXMODE_UNIFIED\n'
        if self.e_flags & self.EF_CUDA_TEXMODE_INDEPENDENT:
            asm += f'# EF_CUDA_TEXMODE_INDEPENDENT\n'
        if self.e_flags & self.EF_CUDA_64BIT_ADDRESS:
            asm += f'# EF_CUDA_64BIT_ADDRESS\n'
        if self.e_flags & self.EF_CUDA_SW_1729687:
            asm += f'# EF_CUDA_SW_1729687\n'
        if self.e_flags & self.EF_CUDA_SW_1729687_v2:
            asm += f'# EF_CUDA_SW_1729687_v2\n'
        asm += f'.compute_{self.virtual_arch}\n'
        asm += f'.sm_{self.arch}\n'
        return asm

    def print_ptx(self):
        cuda_version = f'{self.e_version // 10}.{self.e_version % 10}'
        ptx = f'// CUDA: {cuda_version}\n'

        ptx += f'.version 6.5\n'

        ptx += f'.target sm_{self.arch}'
        if self.e_flags & self.EF_CUDA_TEXMODE_UNIFIED:
            ptx += f', texmode_unified'
        if self.e_flags & self.EF_CUDA_TEXMODE_INDEPENDENT:
            ptx += f', texmode_independent'
        ptx += '\n'

        if self.e_flags & self.EF_CUDA_64BIT_ADDRESS:
            ptx += f'.address_size 64\n'
        else:
            ptx += f'.address_size 32\n'

        return ptx

    def unpack_binary(self, data):
        [self.ei_mag, self.ei_class, self.ei_data, self.ei_version,
         self.ei_osabi, self.ei_abiversion, self.ei_pad] = unpack('4sBBBBB7s', data[:16])

        # 检查 e_ident，确保是64位的cubin
        assert (self.ei_mag == self.ELFMAG)
        assert (self.ei_class == self.ELFCLASS64)
        assert (self.ei_data == self.ELFDATA2LSB)
        assert (self.ei_version == self.EV_CURRENT)
        assert (self.ei_osabi == self.ELFOSABI_CUDA)
        assert (self.ei_abiversion == self.CUDA_ABIVERSION)

        [self.e_type, self.e_machine, self.e_version, self.e_entry,
         self.e_phoff, self.e_shoff, self.e_flags, self.e_ehsize,
         self.e_phentsize, self.e_phnum, self.e_shentsize, self.e_shnum,
         self.e_shstrndx] = unpack('HHIQQQIHHHHHH', data[16:64])

        # 检查 header，确保是64位的cubin
        assert (self.e_type == self.ET_EXEC)
        assert (self.e_machine == self.EM_CUDA)
        assert (self.e_ehsize == 64)
        assert (self.e_phentsize == 56)
        assert (self.e_shentsize == 64)
        assert (self.e_entry == 0)

        # 检查未使用的flags，如果将来的CUDA使用了这些flags，可以及时发现
        assert (self.e_flags & 0xFF00E000 == 0)

        self.arch = self.e_flags & self.EF_CUDA_SM
        self.virtual_arch = (self.e_flags & self.EF_CUDA_VIRTUAL_SM) >> 16
        self.address_size = 64 if self.e_flags & self.EF_CUDA_64BIT_ADDRESS else 32

    def pack_header(self):
        # ELF 64-bit, little endian, version01, ABI33, ABI version7, zero padding
        ident = b'\x7fELF' + b'\x02' + b'\x01' + b'\x01' + b'\x33' + b'\7' + b'\0' * 7
        return pack('<16sHHIQQQIHHHHHH', ident, self.e_type, self.e_machine, self.e_version,
                    self.e_entry, self.e_phoff, self.e_shoff, self.e_flags,
                    self.e_ehsize, self.e_phentsize, self.e_phnum,
                    self.e_shentsize, self.e_shnum, self.e_shstrndx)


class Section:
    SHT_STR = {0: 'NULL', 1: 'PROGBITS', 2: 'SYMTAB', 3: 'STRTAB', 4: 'RELA', 8: 'NOBITS', 9: 'REL',
               0x70000000: 'CUDA_INFO', 0x70000003: 'CUDA_RESOLVED_RELA', 0x7000000B: 'CUDA_RELOCINFO'}
    # todo: CUDA_RELOCINFO
    SHT_VAL = {val: key for (key, val) in SHT_STR.items()}
    SHF_STR = {1: 'W', 2: 'A', 4: 'X'}
    SHF_VAL = {val: key for (key, val) in SHF_STR.items()}

    def __init__(self, iterable=(), **kwargs):
        # Section Header size: Elf64: 64 Bytes | Elf32: 40 Bytes
        # section header string table index
        self.sh_name = 0  # uint32_t
        # the section categorize
        self.sh_type = 0  # uint32_t
        # attributes
        # 对于.text.{kernel}, (sh_flags & 0x01f00000) >> 20 是 bar_count
        self.sh_flags = 0  # Elf32: uint32_t | Elf64: uint64_t
        # memory address, always zero
        self.sh_addr = 0  # Elf32: uint32_t | Elf64: uint64_t
        # file offset
        self.sh_offset = 0  # Elf32: uint32_t | Elf64: uint64_t
        # section's size in bytes
        self.sh_size = 0  # Elf32: uint32_t | Elf64: uint64_t
        # section header table index link
        # .symtab 指向它的.strtab
        # .nv.info*和.text指向.symtab（猜测，都是3，.symtab也刚好是3）
        # 其它的为0
        self.sh_link = 0  # uint32_t
        # extra information
        # 对于.text.{kernel}, (sh_info & 0xff000000) >> 24 是 reg_count, 低位是symbol_table的index
        # 对于.*.{kernel}, sh_info 是 section header table index，指向对应的kernel
        # 对于.symtab，sh_info 是 The first global symbol index,但是cubin里面是 index-1
        self.sh_info = 0  # uint32_t
        # address alignment
        self.sh_addralign = 0  # Elf32: uint32_t | Elf64: uint64_t
        # entry size
        self.sh_entsize = 0  # Elf32: uint32_t | Elf64: uint64_t

        # 其他变量
        self.index = 0
        self.name = b''
        self.data = b''
        self.symbols = []

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        type_ = self.SHT_STR[self.sh_type]
        flags = ''
        for k, v in self.SHF_STR.items():
            flags += v if self.sh_flags & k else '-'
        name = self.name.decode()
        sh_end = self.sh_offset + self.sh_size
        msg = f'Name:{self.name.decode()}, Type:{type_}, File:[{self.sh_offset:#0x}-{sh_end:#0x}]_{self.sh_size}, ' \
              f'EntSize:{self.sh_entsize}, '
        sh_info = self.sh_info
        if name.startswith('.text.'):
            sh_info = sh_info & 0xFFFFFF
            msg += f'RegCount:{(self.sh_info & 0xff000000) >> 24}, BarCount:{(self.sh_flags & 0x01f00000) >> 20}, '
        msg += f'Flags:{flags}, Link:{self.sh_link}, Info:{sh_info} Align:{self.sh_addralign}'
        return msg

    def __eq__(self, other):
        src_size = self.sh_size
        dst_size = other.sh_size
        src_info = self.sh_info & 0xff000000
        dst_info = other.sh_info & 0xff000000
        src_data = b''
        dst_data = b''
        if self.sh_type == self.SHT_VAL['PROGBITS']:
            src_data = self.data
            dst_data = other.data

        # if self.SHT_STR[self.sh_type] in ['STRTAB', 'SYMTAB', 'CUDA_INFO']:
        if self.SHT_STR[self.sh_type] == 'STRTAB':
            src_size = 0
            dst_size = 0

        src = [self.name, self.sh_type, self.sh_flags, self.sh_addr, src_size,
               self.sh_link, src_info, self.sh_addralign, self.sh_entsize, src_data]
        dst = [other.name, other.sh_type, other.sh_flags, other.sh_addr, dst_size,
               other.sh_link, dst_info, other.sh_addralign, other.sh_entsize, dst_data]

        if src != dst:
            print(f'old: {self}')
            print(f'new: {other}')
        return src == dst

    def unpack_binary(self, data):
        [self.sh_name, self.sh_type, self.sh_flags, self.sh_addr, self.sh_offset, self.sh_size, self.sh_link,
         self.sh_info, self.sh_addralign, self.sh_entsize] = unpack('IIQQQQIIQQ', data[:64])

        assert (self.sh_type in self.SHT_STR)
        assert (self.sh_flags & 0xFFFFFFFFFE0FFFF8 == 0)
        assert (self.sh_addr == 0)
        assert (self.sh_link == 0 or self.sh_link == 2 or self.sh_link == 3)
        if self.sh_type == self.SHT_VAL['SYMTAB']:
            assert (self.sh_entsize == 0x18)
        elif self.sh_type == self.SHT_VAL['REL']:
            assert (self.sh_entsize == 0x10)

        self.name = b''
        self.data = b''
        self.symbols = []

    def pack_header(self):
        return pack('<IIQQQQIIQQ', self.sh_name, self.sh_type, self.sh_flags, self.sh_addr, self.sh_offset,
                    self.sh_size, self.sh_link, self.sh_info, self.sh_addralign, self.sh_entsize)


class Symbol:
    STT_STR = {0: 'NOTYPE', 1: 'OBJECT', 2: 'FUNC', 3: 'SECTION', 10: 'CUDA_TEXTURE'}
    STT_VAL = {val: key for (key, val) in STT_STR.items()}
    STB_STR = {0: 'LOCAL', 1: 'GLOBAL', 2: 'WEAK'}
    STB_VAL = {val: key for (key, val) in STB_STR.items()}
    STV_STR = {0: 'DEFAULT', 1: 'INTERNAL', 16: 'CUDA_FUNC'}
    STV_VAL = {val: key for (key, val) in STV_STR.items()}

    def __init__(self, iterable=(), **kwargs):
        # String  table  sections size: Elf64: 24 Bytes | Elf32: 16 Bytes
        # Elf32_Sym:     uint32_t      st_name;
        #                Elf32_Addr    st_value;
        #                uint32_t      st_size;
        #                unsigned char st_info;
        #                unsigned char st_other;
        #                uint16_t      st_shndx;

        # 指向字符串表的索引值
        self.st_name = 0  # uint32_t
        # 符号的类型和属性
        self.st_info = 0  # uint8_t
        # symbol visibility
        self.st_other = 0  # uint8_t
        # the relevant section header table index.
        self.st_shndx = 0  # uint16_t
        # 一个虚拟地址,直接指向符号所在的内存位置
        self.st_value = 0  # uint64_t
        # 符号的大小
        self.st_size = 0  # uint64_t

        # 其他变量
        self.index = 0
        self.name = b''
        self.bind = 0
        self.type = 0

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        type_ = self.STT_STR[self.type]
        bind = self.STB_STR[self.bind]
        vis = self.STV_STR[self.st_other]
        msg = f'Name:{self.name.decode()}, Bind:{bind} Type:{type_}, Visibility:{vis}, Ndx:{self.st_shndx}, ' \
              f'Size:{self.st_size}'
        return msg

    def __eq__(self, other):
        src = [self.name, self.st_info, self.st_other, self.st_value, self.st_size]
        dst = [other.name, other.st_info, other.st_other, other.st_value, other.st_size]

        if src != dst:
            print(f'old: {self}')
            print(f'new: {other}')
        return src == dst

    def unpack_binary(self, data):
        self.st_name, self.st_info, self.st_other, self.st_shndx, self.st_value, self.st_size = unpack(
            'IBBHQQ', data)
        self.name = b''
        self.type = self.st_info & 0xf
        self.bind = self.st_info >> 4

        assert (self.type in self.STT_STR)
        assert (self.bind in self.STB_STR)
        assert (self.st_other in self.STV_STR)

    def pack_entry(self):
        return pack('<IBBHQQ', self.st_name,
                    self.st_info, self.st_other, self.st_shndx, self.st_value, self.st_size)


class Relocation:
    R_TYPE_61 = {43: '32@lo', 44: '32@hi'}
    R_TYPE_75 = {56: '32@lo', 57: '32@hi', 58: '32@fn'}
    R_TYPE = {**R_TYPE_61, **R_TYPE_75}
    R_TYPE_VAL_61 = {val: key for (key, val) in R_TYPE_61.items()}
    R_TYPE_VAL_75 = {val: key for (key, val) in R_TYPE_75.items()}

    def __init__(self, iterable=(), **kwargs):
        # the virtual address of the storage unit affected by the relocation.
        self.r_offset = 0  # Elf32: uint32_t | Elf64: uint64_t
        # symbol table index(Elf32: 8-16位 | Elf64: 高32位) and type(Elf32: 低8位 | Elf64: 低32位)
        self.r_info = 0  # Elf32: uint32_t | Elf64: uint64_t

        # 其他变量
        # Symbol表编号
        self.sym = 0
        # '32@lo': 43, '32@hi': 44 eg: MOV32I R2, 32@lo(test_u8)
        self.type = 0
        self.sym_name = b''

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        msg = f'SymbolName:{self.sym_name}, Type:{self.type:b}, Offset:{self.r_offset:#0x}'
        return msg

    def unpack_binary(self, data):
        self.r_offset, self.r_info = unpack('QQ', data)
        self.sym = self.r_info >> 32
        self.type = self.r_info & 0xffffffff
        assert self.type in self.R_TYPE

    def pack_entry(self):
        return pack('<QQ', self.r_offset, self.r_info)


class RelocationAdd:
    R_TYPE_61 = {43: '32@lo', 44: '32@hi'}
    R_TYPE_75 = {56: '32@lo', 57: '32@hi'}
    R_TYPE = {**R_TYPE_61, **R_TYPE_75}
    R_TYPE_VAL_61 = {val: key for (key, val) in R_TYPE_61.items()}
    R_TYPE_VAL_75 = {val: key for (key, val) in R_TYPE_75.items()}

    def __init__(self, iterable=(), **kwargs):
        # the virtual address of the storage unit affected by the relocation.
        self.r_offset = 0  # Elf32: uint32_t | Elf64: uint64_t
        # symbol table index(Elf32: 8-16位 | Elf64: 高32位) and type(Elf32: 低8位 | Elf64: 低32位)
        self.r_info = 0  # Elf32: uint32_t | Elf64: uint64_t
        self.r_addend = 0  # Elf32: int32_t | Elf64: int64_t

        # 其他变量
        # Symbol表编号
        self.sym = 0
        # '32@lo': 43, '32@hi': 44 eg: MOV32I R2, 32@lo(test_u8)
        self.type = 0
        self.sym_name = b''

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        msg = f'SymbolName:{self.sym_name}, Type:{self.type:b}, Offset:{self.r_offset:#0x}, Addend:{self.r_addend:#0x}'
        return msg

    def unpack_binary(self, data):
        self.r_offset, self.r_info, self.r_addend = unpack('QQq', data)
        self.sym = self.r_info >> 32
        self.type = self.r_info & 0xffffffff
        assert self.type in self.R_TYPE

    def pack_entry(self):
        return pack('<QQq', self.r_offset, self.r_info, self.r_addend)


class Program:
    PT_STR = {1: 'LOAD', 6: 'PHDR'}
    SHT_VAL = {val: key for (key, val) in PT_STR.items()}
    PF_STR = {4: 'R', 2: 'W', 1: 'X'}
    PF_VAL = {val: key for (key, val) in PF_STR.items()}

    def __init__(self, iterable=(), **kwargs):
        # Program Header size: Elf64: 56 Bytes | Elf32: 32 Bytes
        # Elf32_Phdr:    uint32_t   p_type;
        #                Elf32_Off  p_offset;
        #                Elf32_Addr p_vaddr;
        #                Elf32_Addr p_paddr;
        #                uint32_t   p_filesz;
        #                uint32_t   p_memsz;
        #                uint32_t   p_flags;
        #                uint32_t   p_align;

        # what kind of segment:
        # 1 - LOAD: loadable segment
        # 6 - PHDR: program header table
        self.p_type = 0  # uint32_t
        # a bit mask of flags: 0x4 - PF_R; 0x2 - PF_W; 0x1 - PF_X;
        self.p_flags = 0  # uint32_t
        # the offset from the beginning of the file at which the first byte of the segment resides
        self.p_offset = 0  # uint64_t
        # virtual address, always zero
        self.p_vaddr = 0  # uint64_t
        # physical address, always zero
        self.p_paddr = 0  # uint64_t
        # number of bytes in the file image of the segment
        self.p_filesz = 0  # uint64_t
        # number of bytes in the memory image of the segment. shared = 0
        self.p_memsz = 0  # uint64_t
        # bytes aligned in memory and in the file
        self.p_align = 8  # uint64_t

        # 其它变量
        self.section_mapping = []

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        type_ = self.PT_STR[self.p_type]
        flags = ''
        for k, v in self.PF_STR.items():
            flags += v if self.p_flags & k else '-'
        p_end = self.p_offset + self.p_filesz
        msg = f'Type:{type_}, Flags:{flags}, File:[{self.p_offset:#0x}-{p_end:#0x}]_{self.p_filesz}, Mem:{self.p_memsz}'
        if self.section_mapping:
            msg += f', SectionMapping:{self.section_mapping}'
        return msg

    def unpack_binary(self, data):
        [self.p_type, self.p_flags, self.p_offset, self.p_vaddr,
         self.p_paddr, self.p_filesz, self.p_memsz, self.p_align] = unpack('IIQQQQQQ', data[:56])

        assert (self.p_type in self.PT_STR)
        assert (self.p_flags < 8)
        assert (self.p_vaddr == 0)
        assert (self.p_paddr == 0)
        assert (self.p_align == 8)

    def pack_header(self):
        return pack('<IIQQQQQQ', self.p_type, self.p_flags, self.p_offset,
                    self.p_vaddr, self.p_paddr, self.p_filesz, self.p_memsz, self.p_align)


class ELF:
    def __init__(self, iterable=(), **kwargs):
        self.path = ''
        self.header = None
        self.programs = []
        self.sections = []
        self.symbols = []
        self.section_dict = {}
        self.symbol_dict = {}

        self.shstrtab = None
        self.strtab = None
        self.symtab = None

        self.__dict__.update(iterable, **kwargs)

    def __repr__(self):
        msg = f'Path:{self.path}, {self.header}, Sections:{[n.decode() for n in self.section_dict.keys()]}, ' \
              f'Symbols:{[n.decode() for n in self.symbol_dict.keys()]}'
        return msg

    def load(self, path):
        self.path = path
        with open(path, 'rb') as f:
            data = f.read()

        # Read in ELF Headers
        self.header = Header()
        self.header.unpack_binary(data)

        # Read in Section
        for i in range(self.header.e_shnum):
            section = Section()
            begin = self.header.e_shoff + i * self.header.e_shentsize
            end = begin + self.header.e_shentsize
            section.unpack_binary(data[begin:end])
            self.sections.append(section)

            if section.sh_size and section.sh_type != Section.SHT_VAL['NOBITS']:
                section.data = data[section.sh_offset:section.sh_offset + section.sh_size]

            # Read in symbols
            if section.sh_type == Section.SHT_VAL['SYMTAB']:
                offset = 0
                while offset < section.sh_size:
                    symbol = Symbol()
                    symbol.unpack_binary(section.data[offset:offset + section.sh_entsize])
                    offset += section.sh_entsize
                    self.symbols.append(symbol)

        # Update section headers with their names.
        sh_string_table = self.sections[self.header.e_shstrndx].data
        for section in self.sections:
            section.name = sh_string_table[section.sh_name:].split(b'\0', 1)[0]
            self.section_dict[section.name] = section

        # Update symbols with their names
        symbol_string_table = self.section_dict[b'.strtab'].data
        for symbol in self.symbols:
            symbol.name = symbol_string_table[symbol.st_name:].split(b'\0', 1)[0]
            self.symbol_dict[symbol.name] = symbol

            # Attach symbol to section
            section = self.sections[symbol.st_shndx]
            section.symbols.append(symbol)

        # Read in Program Headers
        for i in range(self.header.e_phnum):
            program = Program()
            begin = self.header.e_phoff + i * self.header.e_phentsize
            end = begin + self.header.e_phentsize
            program.unpack_binary(data[begin:end])
            for section in self.sections:
                if program.p_offset <= section.sh_offset < (program.p_offset + program.p_memsz):
                    program.section_mapping.append(section.name)
            self.programs.append(program)

    def write(self, path):
        """
            Write data to file.
            Order:
               1. Header.
               2. shstrtab, strtab, symtab, .nv.info.
               3. info_secs, const_secs, text_secs, smem_secs
               4. shdrs.
               5. phdrs.
        """
        with open(path, 'wb') as file:
            offset = 0
            header_data = self.header.pack_header()
            offset += file.write(header_data)
            for sec in self.sections:
                begin = align_offset(offset, sec.sh_addralign)
                if begin > offset:
                    offset += file.write(b'\0' * (begin - offset))
                offset += file.write(sec.data)

            begin = align_offset(offset, 8)
            if begin > offset:
                offset += file.write(b'\0' * (begin - offset))
            for sec in self.sections:
                header_data = sec.pack_header()
                offset += file.write(header_data)
            for pro in self.programs:
                offset += file.write(pro.pack_header())
            ph_end = self.header.e_phoff + self.header.e_phnum * self.header.e_phentsize
            assert offset == ph_end
