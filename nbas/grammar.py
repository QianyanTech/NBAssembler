import re
import os


# include nested files
def process_include(str_, asm_path, define_dict):
    def include_file(x):
        path = os.path.join(os.path.dirname(asm_path), x.group('file'))
        with open(path, 'r') as fd:
            source = fd.read()
        define_dict['out'] = ''
        if path.endswith('.py'):
            exec(source, define_dict)
            source = define_dict['out']
        return source

    str_ = re.sub(INCLUDE_RE, include_file, str_)
    return str_


# run embedded python code
def process_python_code(str_, define_dict):
    def run_python_code(x):
        define_dict['out'] = ''
        source = x.group('code')
        if '\n' in source:
            exec(source, define_dict)
            out_ = define_dict['out']
        else:
            out_ = eval(source, define_dict)
        return out_

    str_ = re.sub(PYTHON_RE, run_python_code, str_)
    return str_


def strip_comment(str_):
    # 去掉注释
    str_ = re.sub(r'#.*', '', str_)
    str_ = re.sub(r'//.*', '', str_)
    str_ = re.sub(r'/\*.+?\*/', '', str_, flags=re.DOTALL)
    # 去掉;前的空白
    str_ = re.sub(r'\s+;', ';', str_)
    # 去掉行尾空白
    str_ = re.sub(r'[ \t]+\n', '\n', str_)
    # 去掉空行
    str_ = re.sub(r'^\s*\n', '', str_, flags=re.MULTILINE)
    # section之间加空行
    str_ = re.sub(r'\n\.', '\n\n.', str_)
    # 格式化缩进
    str_ = re.sub(r'[ \t]{2,}', '    ', str_)
    return str_


def strip_space(str_):
    # 去掉注释
    str_ = re.sub(r'#.*', '', str_)
    str_ = re.sub(r'//.*', '', str_)
    str_ = re.sub(r'/\*.+?\*/', '', str_, flags=re.DOTALL)
    # 去掉;前的空白
    str_ = re.sub(r'\s+;', ';', str_)
    # 多个空白变成一个空格
    str_ = re.sub(r'[ \t]+', ' ', str_)
    # 去掉空行
    str_ = re.sub(r'^\s*\n', '', str_, flags=re.MULTILINE)
    # 去掉行尾空白
    str_ = re.sub(r'[ \t]+\n', '\n', str_)
    # 去除末尾最后一个换行
    str_ = re.sub(r'\n$', '', str_)
    return str_


INCLUDE_RE = rf'(?sm:^\.include\s+"(?P<file>[^"]+?)"\n?)'
PYTHON_RE = rf'(?sm:{{(?P<code>.*?)}})'
SCHED_RE = rf'(?sm:^\.sched.+?\.end_sched)'

REG_NAME_RE = rf'(?P<type>U?[RP])_(?P<name>[a-zA-Z_]\w*)_?(?P<offset>\d+)?'
CONST_NAME_RE = rf'c\[(?P<const>(?P<name>[a-zA-Z_]\w*)(?:\+(?P<offset>\d+))?)\]'
GLOBAL_NAME_RE = rf'(?P<type>32@(lo|hi))\((?P<name>[a-zA-Z_]\w*)\)'

COMPUTE_RE = rf'(?sm:^\.compute_(?P<compute>[0-9]+))'
ARCH_RE = rf'(?sm:^\.sm_(?P<arch>[0-9]+))'
ALIGN_RE = rf'\.align\s+(?P<align>\d+)'
DATA_RE = rf'(?sm:^\.(?P<type>constant2|constant|global):\s*(?P<name>[a-zA-Z_]\w*)\s+' \
          rf'{ALIGN_RE}\s+(?P<data>.+?(?=^\.)|.+))'
DATA_ROW_RE = rf'\s*\.(?P<type>zero|byte|short|word|quad)\s+(?P<data>.+)'
KERNEL_RE = rf'(?sm:^\.kernel:\s*(?P<name>[a-zA-Z_]\w*)\s+(?P<data>.+?(?=^\.[^L])|.+))'

LABEL_RE = r'(?P<label>L_[0-9a-zA-Z_]+)'
CTRL_RE = r'(?P<ctrl>[KS\-]:[0-9a-fA-F\-]{2}:[1-6\-]:[1-6\-]:[\-yY]:[0-9a-fA-F\-])'

ADDR_RE = r'(/\*(?P<addr>[0-9a-f]+)\*/)'
PRED_RE = r'(?P<pred>@(?P<pred_not>!)?U?P(?P<pred_reg>([T\d]|_[a-zA-Z_]\w*_?\d+)))'
INST_RE = rf'(({PRED_RE}\s+)?(?P<op>\w+)(?P<rest>[^;]*;))'
CODE_RE = r'(/\* (?P<code>0x[0-9a-f]+) \*/)'
REUSE_RE = r'(#\s*(?P<reuse>[1-4\-]{4}))'
SASS_RE = rf'{ADDR_RE}\s+{INST_RE}\s+{CODE_RE}'
ASM_RE = rf'^\s*{ADDR_RE}?\s*{CTRL_RE}\s+{INST_RE}\s*{CODE_RE}?\s*{REUSE_RE}'


def get_b(value, shift):
    m = re.search(r'^B(\d+)$', value)
    if m is None:
        raise Exception(f'Bad B register name: {value}.')
    val = int(m.group(1))
    if val >= 16:
        raise Exception(f'B register index {value} is greater than 15.')
    return val << shift


def get_r(value, shift):
    m = re.search(r'^R(\d+|Z)$', value)
    if m is None:
        raise Exception(f'Bad register name: {value}.')
    if m.group(1) == 'Z':
        val = 0xff
    else:
        val = int(m.group(1))
        if val >= 255:
            raise Exception(f'Register index {value} is greater than 254.')
    return val << shift


def get_ur(value, shift):
    m = re.search(r'^UR(\d+|Z)$', value)
    if m is None:
        raise Exception(f'Bad uniform register name: {value}.')
    if m.group(1) == 'Z':
        val = 0x3f
    else:
        val = int(m.group(1))
        if val >= 63:
            raise Exception(f'Uniform Register index {value} is greater than 62.')
    return val << shift


def get_c(value, shift):
    return ((int(value, base=0) >> 2) & 0x7fff) << shift


def get_u(value, shift, mask):
    value = int(value, base=0)
    if value > mask:
        raise Exception(f'Immediate value {value} out of range {mask}.\n')
    return (value & mask) << shift


def get_i(value, shift, mask, sign=0x0100000000000000):
    value = int(value, base=0)
    t = abs(value)
    # if -(mask >> 1) - 1 > value or value > (mask >> 1):
    if value > (mask << 1) + 1:
        raise Exception(f'Immediate value {value} out of range {mask}.\n')
    elif value > mask:
        return ((value & mask) << shift) ^ sign
    elif t > mask + 1:
        raise Exception(f'Immediate value {value} out of range {mask}.\n')
    return (value & mask) << shift


def get_p(value, shift):
    m = re.search(r'^U?P(\d+|T)$', value)
    if m is None:
        raise Exception(f'Bad predicate name: {value}\n')
    if m.group(1) == 'T':
        val = 7
    else:
        val = int(m.group(1))
    if val > 7:
        raise Exception(f'Predicate index {value} is greater than 7.\n')
    return val << shift


operands = {
    # Pascal
    'i8w8': lambda value: get_i(value, 8, 0xf) ^ 0x0000100000000000,
    'i20': lambda value: get_i(value, 20, 0x7ffff),
    'i20w6': lambda value: get_i(value, 20, 0x3f),
    'i20w8': lambda value: get_i(value, 20, 0xff) ^ 0x0000000010000000,
    'i20w12': lambda value: get_i(value, 20, 0xfff),
    'i20w24': lambda value: get_i(value, 20, 0xffffff),
    'i20w32': lambda value: get_i(value, 20, 0xffffffff),
    'i28w8': lambda value: get_i(value, 28, 0xff),
    'i28w5': lambda value: get_i(value, 28, 0x1f),
    'i28w20': lambda value: get_i(value, 28, 0xfffff),
    'i30w22': lambda value: get_i(value, 30, 0xffffff) >> 2,
    'i34w13': lambda value: get_i(value, 34, 0x1fff) ^ 0x0000000020000000,
    'i39w5': lambda value: get_i(value, 39, 0x1f),
    'i48w8': lambda value: get_i(value, 48, 0xff),
    'i51w5': lambda value: get_i(value, 51, 0x1f),
    'c20': lambda value: get_c(value, 20),
    'c34': lambda value: (int(value, base=0) << 34),
    'c36': lambda value: (int(value, base=0) << 36),
    'r0': lambda value: get_r(value, 0),
    'r8': lambda value: get_r(value, 8),
    'r8a': lambda value: 0x000000000000ff00,
    'r20': lambda value: get_r(value, 20),
    'r39': lambda value: get_r(value, 39),
    'r39a': lambda value: get_r(value, 39),
    'p0': lambda value: get_p(value, 0),
    'p3': lambda value: get_p(value, 3),
    'p12': lambda value: get_p(value, 12),
    'p29': lambda value: get_p(value, 29),
    'p39': lambda value: get_p(value, 39),
    'p45': lambda value: get_p(value, 45),
    'p48': lambda value: get_p(value, 48),
    'p48q': lambda value: get_p(value, 48) ^ 0x0007000000000000,
    'p58': lambda value: get_p(value, 58),
    # Turing
    'i32': lambda value: get_i(value, 32, 0xffffffff, 0x8000000000000000),
    'i32a4': lambda value: get_i(value, 32, 0x3fffffffffffc, 0x8000000000000000),
    'i40w24': lambda value: get_i(value, 40, 0xffffff, 0x8000000000000000),
    'i38w6': lambda value: get_i(value, 38, 0x3f, 0),
    'i38w16': lambda value: get_i(value, 38, 0xffff, 0x20000000000000),
    'i40w13': lambda value: get_i(value, 40, 0x1ffff, 0),
    'i54w4': lambda value: get_i(value, 54, 0xf, 0),
    'i72w4': lambda value: get_i(value, 72, 0xf, 0),
    'i75w5': lambda value: get_i(value, 75, 0x1f, 0),
    'i72w8': lambda value: get_i(value, 72, 0xff, 0),
    'c40': lambda value: get_c(value, 40),
    'c54': lambda value: (int(value, base=0) << 54),
    'b16': lambda value: get_b(value, 16),
    'r16': lambda value: get_r(value, 16),
    'r24': lambda value: get_r(value, 24),
    'r32': lambda value: get_r(value, 32),
    'r64': lambda value: get_r(value, 64),
    'ur16': lambda value: get_ur(value, 16),
    'ur24': lambda value: get_ur(value, 24),
    'ur32': lambda value: get_ur(value, 32),
    'ur64': lambda value: get_ur(value, 64),
    'p64q': lambda value: get_p(value, 64) ^ 0x70000000000000000,
    'p68': lambda value: get_p(value, 68),
    'p77': lambda value: get_p(value, 77),
    'p81': lambda value: get_p(value, 81),
    'p84': lambda value: get_p(value, 84),
    'p87': lambda value: get_p(value, 87),
    'up77': lambda value: get_p(value, 77),
    'up81': lambda value: get_p(value, 81),
    'up84': lambda value: get_p(value, 84),
    'up87': lambda value: get_p(value, 87),
}

# these ops need to be converted from absolute addresses to relative in the sass output by cuobjdump
rel_jump_op_61 = [
    'BRA', 'SSY', 'CAL', 'PBK', 'PCNT',
]

rel_jump_op_75 = [
    'BRA', 'SSY', 'CAL', 'PBK', 'PCNT',
    'BSSY', 'CALL', 'RET',  # Turing
]
# these ops use absolute addresses
abs_jump_op = ['JCAL', ]

jump_op_61 = abs_jump_op + rel_jump_op_61
jump_op_75 = abs_jump_op + rel_jump_op_75

hexx = fr'0[xX][0-9a-fA-F]+'
iaddr = fr'\d+[xX]<[^>]+>'
immed = fr'{hexx}|{iaddr}|\d+'
# reg = fr'[a-zA-Z_]\w*'
reg = fr'R[Z0-9]+'
noPred = fr'(?P<noPred>)'

# operands
i20w24 = fr'(?P<i20w24>\-?{immed})'
i20w32 = fr'(?P<i20w32>\-?{immed})'
i28w20 = fr'(?P<i28w20>\-?{immed})'
i30w22 = fr'(?P<i30w22>\-?{immed})'
i28w5 = fr'(?P<i28w5>{immed})'
i39w5 = fr'(?P<i39w5>{immed})'
i8w8 = fr'(?P<i8w8>{immed})'
i20w6 = fr'(?P<i20w6>{immed})'
i28w8 = fr'(?P<i28w8>{immed})'
i20w8 = fr'(?P<i20w8>{immed})'
i34w13 = fr'(?P<i34w13>{immed})'
i48w8 = fr'(?P<i48w8>{immed})'
i51w5 = fr'(?P<i51w5>{immed})'

i20 = fr'(?P<i20>(?P<neg>\-)?{immed})(?P<i20neg>\.NEG)?'

c20 = fr'(?P<c20neg>\-)?(?P<c20abs>\|)?c\[(?P<c34>{hexx})\]\s*\[(?P<c20>{hexx})\]\|?' \
      fr'(?:\.(?P<c20part>H0|H1|B0|B1|B2|B3))?'

r0 = fr'(?P<r0>{reg})(?P<CC>\.CC)?'
r0nc = fr'(?P<r0>{reg})'
r8 = fr'(?P<r8neg>\-)?(?P<r8abs>\|)?(?P<r8>{reg})\|?' \
     fr'(?:\.(?P<r8part>H0|H1|B0|B1|B2|B3|H0_H0|H1_H1|F32))?(?P<reuse1>\.reuse)?'
r8n37 = fr'(?P<r8neg37>\-)?(?P<r8abs>\|)?(?P<r8>{reg})\|?' \
        fr'(?:\.(?P<r8part>H0|H1|B0|B1|B2|B3|H0_H0|H1_H1|F32))?(?P<reuse1>\.reuse)?'
r8n45 = fr'(?P<r8neg45>\-)?(?P<r8abs>\|)?(?P<r8>{reg})\|?' \
        fr'(?:\.(?P<r8part>H0|H1|B0|B1|B2|B3|H0_H0|H1_H1|F32))?(?P<reuse1>\.reuse)?'
r20 = fr'(?P<r20neg>\-)?(?P<r20abs>\|)?(?P<r20>{reg})\|?' \
      fr'(?:\.(?P<r20part>H0|H1|B0|B1|B2|B3|H0_H0|H1_H1))?(?P<reuse2>\.reuse)?'
r39 = fr'(?P<r39neg>\-)?(?P<r39>{reg})(?:\.(?P<r39part>H0|H1|H0_H0|H1_H1|F32))?(?P<reuse3>\.reuse)?'
r39s20 = fr'(?P<r20neg>\-)?(?P<r20abs>\|)?(?P<r39s20>(?P<r39>{reg}))\|?(?:\.(?P<r39part>H0|H1))?(?P<reuse2>\.reuse)?'
r39a = fr'(?P<r39a>(?P<r39>{reg}))(?P<reuse3>\.reuse)?'

addr = fr'\[(?:(?P<r8a>(?P<r8>{reg})))?(?:\s*\+?\s*{i20w24})?\]'
addr2 = fr'\[(?:(?P<r8a>(?P<r8>{reg})))?(?:\s*\+?\s*{i28w20})?\]'
addr3 = fr'\[(?:(?P<r8a>(?P<r8>{reg})))?(?:\s*\+?\s*{i30w22})?\]'
ldc = fr'c\[(?P<c36>{hexx})\]\s*{addr}'

P = fr'P[0-6T]'
p0 = fr'(?P<p0>{P})'
p3 = fr'(?P<p3>{P})'
p12 = fr'(?P<p12not>\!)?(?P<p12>{P})'
p29 = fr'(?P<p29not>\!)?(?P<p29>{P})'
p39 = fr'(?P<p39not>\!)?(?P<p39>{P})'
p45 = fr'(?P<p45>{P})'
p48 = fr'(?P<p48>{P})'
p48q = fr'(?P<p48q>{P})'
p58 = fr'(?P<p58>{P})'

# flags
atom = fr'(?P<E>\.E)?(?:\.(?P<mode>ADD|MIN|MAX|INC|DEC|AND|OR|XOR|EXCH|CAS))' \
       fr'(?P<type>|\.S32|\.U64|\.F(?:16x2|32)\.FTZ\.RN|\.S64|\.64)'
sr = fr'(?P<sr>SR\S+)'
shf = fr'(?P<W>\.W)?(?:\.(?P<type>U64|S64))?(?P<HI>\.HI)?'
mem_cache = fr'(?P<E>\.E)?(?P<U>\.U)?(?:\.(?P<cache>CG|CI|CS|CV|IL|WT|LU))?'
mem_type = fr'(?:\.(?P<type>U8|S8|U16|S16|32|64|128))?'
rnd = fr'(?:\.(?P<rnd>RN|RM|RP|RZ))?'
round_ = fr'(?:\.(?P<round>ROUND|FLOOR|CEIL|TRUNC))?'
hilo = fr'(?:\.(?P<mode>XHI|XLO))?'
x2x = fr'\.(?P<destSign>F|U|S)(?P<destWidth>8|16|32|64)\.(?P<srcSign>F|U|S)(?P<srcWidth>8|16|32|64)'
prmt = fr'(?:\.(?P<mode>F4E|B4E|RC8|ECL|ECR|RC16))?'
shfl = fr"\.(?P<mode>IDX|UP|DOWN|BFLY)"
mbar = fr'\.(?P<mode>CTA|GL|SYS)'
icmp = fr'(?:\.(?P<cmp>LT|EQ|LE|GT|NE|GE))'
u32 = fr'(?P<U32>\.U32)?'
ftz = fr'(?P<FTZ>\.FTZ)?'
sat = fr'(?P<SAT>\.SAT)?'
X = fr'(?P<X>\.X)?'
X38 = fr'(?P<X38>\.X)?'
X46 = fr'(?P<X46>\.X)?'
bool_ = fr'(?:\.(?P<bool>AND|OR|XOR|PASS_B))'
bool2 = fr'(?:\.(?P<bool2>AND|OR|XOR))'
func = fr'\.(?P<func>COS|SIN|EX2|LG2|RCP|RSQ|RCP64H|RSQ64H)'
lopz = fr'(?:\.(?P<z>NZ|Z) {p48q},)'
add3 = fr'(?:\.(?P<type>X|RS|LS))?'
xmad = fr'(?:\.(?P<type1>U16|S16))?(?:\.(?P<type2>U16|S16))?(?:\.(?P<mode>MRG|PSL\.CHI|PSL\.CLO|PSL|CHI|CLO|CSFU))' \
       fr'?(?P<CBCC>\.CBCC)?'
xmadc = fr'(?:\.(?P<type1>U16|S16))?(?:\.(?P<type2>U16|S16))?(?:\.(?P<modec>MRG|PSL\.CLO|PSL|CHI|CLO|CSFU))' \
        fr'?(?P<CBCC>\.CBCC)?'
dbar_sb = fr'(?P<SB>SB0|SB1|SB2|SB3|SB4|SB5)'
dbar_db = r'(\{(?P<db5>5)?,?(?P<db4>4)?,?(?P<db3>3)?,?(?P<db2>2)?,?(?P<db1>1)?,?(?P<db0>0)?\})'
vote = fr'\.(?P<mode>ALL|ANY|EQ)'
idp = fr'\.(?P<mode>2A|4A)(?P<part>|\.HI|\.LO)\.(?P<type1>U8|S8|U16|S16)\.(?P<type2>U8|S8)'
r2p = rf'(?P<r2p>PR|CC)'

# class: hardware resource that shares characteristics with types
# lat  : pipeline depth where relevent, placeholder for memory ops
# blat : barrier latency, typical fetch time for memory operations. Highly variable.
# rlat : operand read latency for memory ops
# rhold: clock cycles that a memory op typically holds onto a register before it's free to be written by another op.
# tput : throughput, clock cycles an op takes when two ops of the same class are issued in succession.
# dual : whether this instruction type can be dual issued
# reuse: whether this instruction type accepts register reuse flags.

# Some of these values are guesses and need to be updated from micro benchmarks.
# We may need to split these classes up further.
s2r_t = {'class': 's2r', 'lat': 2, 'blat': 25, 'rlat': 0, 'rhold': 0, 'tput': 1, 'dual': 0, 'reuse': 0}
smem_t = {'class': 'mem', 'lat': 2, 'blat': 30, 'rlat': 2, 'rhold': 20, 'tput': 1, 'dual': 1, 'reuse': 0}
gmem_t = {'class': 'mem', 'lat': 2, 'blat': 200, 'rlat': 4, 'rhold': 20, 'tput': 1, 'dual': 1, 'reuse': 0}
x32_t = {'class': 'x32', 'lat': 6, 'blat': 0, 'rlat': 0, 'rhold': 0, 'tput': 1, 'dual': 0, 'reuse': 1}
x64_t = {'class': 'x64', 'lat': 2, 'blat': 128, 'rlat': 0, 'rhold': 0, 'tput': 128, 'dual': 0, 'reuse': 1}
shft_t = {'class': 'shift', 'lat': 6, 'blat': 0, 'rlat': 0, 'rhold': 0, 'tput': 2, 'dual': 0, 'reuse': 1}
cmp_t = {'class': 'cmp', 'lat': 13, 'blat': 0, 'rlat': 0, 'rhold': 0, 'tput': 2, 'dual': 0, 'reuse': 1}
qtr_t = {'class': 'qtr', 'lat': 8, 'blat': 0, 'rlat': 4, 'rhold': 0, 'tput': 1, 'dual': 1, 'reuse': 0}
rro_t = {'class': 'rro', 'lat': 2, 'blat': 0, 'rlat': 0, 'rhold': 0, 'tput': 1, 'dual': 0, 'reuse': 0}
vote_t = {'class': 'vote', 'lat': 2, 'blat': 0, 'rlat': 0, 'rhold': 0, 'tput': 1, 'dual': 0, 'reuse': 0}

instr_type_75 = {
    'x32': {'lat': 5, 'reuse': 1, },
}

grammar_61 = {
    # Floating Point Instructions
    'MUFU': [  # FP Multi-Function Operator 参考ptx的 cos|sin|ex2|lg2|rcp|rsqrt等
        {'type': qtr_t, 'code': 0x5080000000000000, 'rule': rf'MUFU{func} {r0}, {r8};'}],

    # Integer Instructions
    'BFE': [  # bfe
        {'type': shft_t, 'code': 0x3801000000000000, 'rule': rf'BFE{u32} {r0}, {r8}, {i20};'},
        {'type': shft_t, 'code': 0x4c01000000000000, 'rule': rf'BFE{u32} {r0}, {r8}, {c20};'},
        {'type': shft_t, 'code': 0x5c01000000000000, 'rule': rf'BFE{u32} {r0}, {r8}, {r20};'}],
    'BFI': [  # bfi
        {'type': shft_t, 'code': 0x36f0000000000000, 'rule': rf'BFI {r0}, {r8}, {i20}, {r39};'},
        {'type': shft_t, 'code': 0x53f0000000000000, 'rule': rf'BFI {r0}, {r8}, {r20}, {c20};'},
        {'type': shft_t, 'code': 0x5bf0000000000000, 'rule': rf'BFI {r0}, {r8}, {r20}, {r39};'}],
    'FLO': [  # clz
        {'type': s2r_t, 'code': 0x3830000000000000, 'rule': rf'FLO\.U32 {r0}, {i20};'},
        {'type': s2r_t, 'code': 0x4c30000000000000, 'rule': rf'FLO\.U32 {r0}, {c20};'},
        {'type': s2r_t, 'code': 0x5c30000000000000, 'rule': rf'FLO\.U32 {r0}, {r20};'}],
    'IADD': [  # add
        {'type': x32_t, 'code': 0x3810000000000000, 'rule': rf'IADD{sat}{X} {r0}, {r8}, {i20};'},
        {'type': x32_t, 'code': 0x4c10000000000000, 'rule': rf'IADD{sat}{X} {r0}, {r8}, {c20};'},
        {'type': x32_t, 'code': 0x5c10000000000000, 'rule': rf'IADD{sat}{X} {r0}, {r8}, {r20};'}],
    'IADD32I': [  # add
        {'type': x32_t, 'code': 0x1c00000000000000, 'rule': rf'IADD32I{X} {r0}, {r8}, {i20w32};'}],
    'IADD3': [  # add ls: DST = add_with_carry(((SRC1 + SRC2) << 16), SRC3)
        {'type': x32_t, 'code': 0x38c0000000000000, 'rule': rf'IADD3{add3} {r0}, {r8}, {i20}, {r39};'},
        {'type': x32_t, 'code': 0x4cc0000000000000, 'rule': rf'IADD3{add3} {r0}, {r8}, {c20}, {r39};'},
        {'type': x32_t, 'code': 0x5cc0000000000000, 'rule': rf'IADD3{add3} {r0}, {r8}, {r20}, {r39};'}],
    'IMNMX': [  # max min
        {'type': shft_t, 'code': 0x3821000000000000, 'rule': rf'IMNMX{u32}{hilo} {r0}, {r8}, {i20}, {p39};'},
        {'type': shft_t, 'code': 0x4c21000000000000, 'rule': rf'IMNMX{u32}{hilo} {r0}, {r8}, {c20}, {p39};'},
        {'type': shft_t, 'code': 0x5c21000000000000, 'rule': rf'IMNMX{u32}{hilo} {r0}, {r8}, {r20}, {p39};'}],
    'ISCADD': [  # mad 或 ld st内置
        {'type': shft_t, 'code': 0x3818000000000000, 'rule': rf'ISCADD {r0}, {r8}, {i20}, {i39w5};'},
        {'type': shft_t, 'code': 0x4c18000000000000, 'rule': rf'ISCADD {r0}, {r8}, {c20}, {i39w5};'},
        {'type': shft_t, 'code': 0x5c18000000000000, 'rule': rf'ISCADD {r0}, {r8}, {r20}, {i39w5};'}],
    'LEA': [  # mad 或 ld st内置
        {'type': shft_t, 'code': 0x1807000000000000,
         'rule': rf'LEA\.HI{X}( {p48q},)? {r0}, {r8}, {c20}, {r39}(, {i51w5})?;'},
        {'type': cmp_t, 'code': 0x36d7000000000000,
         'rule': rf'LEA{X46}( {p48q},)? {r0}, {r8n45}, {i20}(, {i39w5})?;'},
        {'type': cmp_t, 'code': 0x4bd7000000000000,
         'rule': rf'LEA{X46}( {p48q},)? {r0}, {r8n45}, {c20}(, {i39w5})?;'},
        {'type': cmp_t, 'code': 0x5bd7000000000000,
         'rule': rf'LEA{X46}( {p48q},)? {r0}, {r8n45}, {r20}(, {i39w5})?;'},
        {'type': shft_t, 'code': 0x5bdf000000000000,
         'rule': rf'LEA\.HI{X38}( {p48q},)? {r0}, {r8n37}, {r20}, {r39}(, {i28w5})?;'}],
    'POPC': [  # popc
        {'type': s2r_t, 'code': 0x5c08000000000000, 'rule': rf'POPC {r0}, {r20};'}],
    'XMAD': [  # mad
        {'type': x32_t, 'code': 0x3600000000000000, 'rule': rf'XMAD{xmad} {r0}, {r8}, {i20}, {r39};'},
        {'type': x32_t, 'code': 0x5b00000000000000, 'rule': rf'XMAD{xmad} {r0}, {r8}, {r20}, {r39};'},
        {'type': x32_t, 'code': 0x5100000000000000, 'rule': rf'XMAD{xmad} {r0}, {r8}, {r39s20}, {c20};'},
        {'type': x32_t, 'code': 0x4e00000000000000, 'rule': rf'XMAD{xmadc} {r0}, {r8}, {c20}, {r39};'}],
    'IDP': [  # dp4a dp2a
        {'type': x32_t, 'code': 0x53d8000000000000, 'rule': rf'IDP{idp} {r0}, {r8}, {c20}, {r39};'},
        {'type': x32_t, 'code': 0x53f8000000000000, 'rule': rf'IDP{idp} {r0}, {r8}, {r20}, {r39};'}],

    # Comparison and Selection Instructions
    'ISET': [  # set
        {'type': shft_t, 'code': 0x3651000000000000, 'rule': rf'ISET{icmp}{u32}{X}{bool_} {r0}, {r8}, {i20}, {p39};'},
        {'type': shft_t, 'code': 0x4b51000000000000, 'rule': rf'ISET{icmp}{u32}{X}{bool_} {r0}, {r8}, {c20}, {p39};'},
        {'type': shft_t, 'code': 0x5b51000000000000, 'rule': rf'ISET{icmp}{u32}{X}{bool_} {r0}, {r8}, {r20}, {p39};'}],
    'ISETP': [  # setp
        {'type': cmp_t, 'code': 0x3661000000000000,
         'rule': rf'ISETP{icmp}{u32}{X}{bool_} {p3}, {p0}, {r8}, {i20}, {p39};'},
        {'type': cmp_t, 'code': 0x4b61000000000000,
         'rule': rf'ISETP{icmp}{u32}{X}{bool_} {p3}, {p0}, {r8}, {c20}, {p39};'},
        {'type': cmp_t, 'code': 0x5b61000000000000,
         'rule': rf'ISETP{icmp}{u32}{X}{bool_} {p3}, {p0}, {r8}, {r20}, {p39};'}],
    'ICMP': [  # slct
        {'type': cmp_t, 'code': 0x3641000000000000, 'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, {i20}, {r39};'},
        {'type': cmp_t, 'code': 0x4b41000000000000, 'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, {c20}, {r39};'},
        {'type': cmp_t, 'code': 0x5b41000000000000, 'rule': rf'ICMP{icmp}{u32} {r0}, {r8}, {r20}, {r39};'}],

    # Logic and Shift Instructions
    'LOP': [  # and or xor not
        {'type': x32_t, 'code': 0x3847000000000000,
         'rule': rf'LOP{bool_}{X}{lopz}? {r0}, (?P<INV8>~)?{r8}, {i20}(?P<TINV>\.INV)?;'},
        {'type': x32_t, 'code': 0x4c47000000000000,
         'rule': rf'LOP{bool_}{X}{lopz}? {r0}, (?P<INV8>~)?{r8}, (?P<INV>~)?{c20};'},
        {'type': x32_t, 'code': 0x5c47000000000000,
         'rule': rf'LOP{bool_}{X}{lopz}? {r0}, (?P<INV8>~)?{r8}, (?P<INV>~)?{r20};'}],
    'LOP32I': [  # and or xor not
        {'type': x32_t, 'code': 0x0400000000000000, 'rule': rf'LOP32I{bool_} {r0}, (?P<INV8>~)?{r8}, {i20w32};'}],
    'LOP3': [  # lop3
        {'type': x32_t, 'code': 0x5be7000000000000, 'rule': rf'LOP3\.LUT {r0}, {r8}, {r20}, {r39}, {i28w8};'},
        {'type': x32_t, 'code': 0x3c00000000000000, 'rule': rf'LOP3\.LUT {r0}, {r8}, {i20}, {r39}, {i48w8};'},
        {'type': x32_t, 'code': 0x0200000000000000, 'rule': rf'LOP3\.LUT {r0}, {r8}, {c20}, {r39}, {i48w8};'}],
    'SHF': [  # shf
        {'type': shft_t, 'code': 0x36f8000000000000, 'rule': rf'SHF\.L{shf} {r0}, {r8}, {i20}, {r39};'},
        {'type': shft_t, 'code': 0x38f8000000000000, 'rule': rf'SHF\.R{shf} {r0}, {r8}, {i20}, {r39};'},
        {'type': shft_t, 'code': 0x5bf8000000000000, 'rule': rf'SHF\.L{shf} {r0}, {r8}, {r20}, {r39};'},
        {'type': shft_t, 'code': 0x5cf8000000000000, 'rule': rf'SHF\.R{shf} {r0}, {r8}, {r20}, {r39};'}],
    'SHL': [  # shl
        {'type': shft_t, 'code': 0x3848000000000000, 'rule': rf'SHL(?P<W>\.W)? {r0}, {r8}, {i20};'},
        {'type': shft_t, 'code': 0x4c48000000000000, 'rule': rf'SHL(?P<W>\.W)? {r0}, {r8}, {c20};'},
        {'type': shft_t, 'code': 0x5c48000000000000, 'rule': rf'SHL(?P<W>\.W)? {r0}, {r8}, {r20};'}],
    'SHR': [  # shr
        {'type': shft_t, 'code': 0x3829000000000000, 'rule': rf'SHR{u32} {r0}, {r8}, {i20};'},
        {'type': shft_t, 'code': 0x4c29000000000000, 'rule': rf'SHR{u32} {r0}, {r8}, {c20};'},
        {'type': shft_t, 'code': 0x5c29000000000000, 'rule': rf'SHR{u32} {r0}, {r8}, {r20};'}],

    # Movement Instructions
    'MOV': [  # mov
        {'type': x32_t, 'code': 0x3898078000000000, 'rule': rf'MOV {r0}, {i20};'},
        {'type': x32_t, 'code': 0x4c98078000000000, 'rule': rf'MOV {r0}, {c20};'},
        {'type': x32_t, 'code': 0x5c98078000000000, 'rule': rf'MOV {r0}, {r20};'}],
    'MOV32I': [  # mov
        {'type': x32_t, 'code': 0x010000000000f000, 'rule': rf'MOV32I {r0}, {i20w32};'}],
    'SHFL': [  # shfl.sync
        {'type': smem_t, 'code': 0xef10000000000000,
         'rule': rf'SHFL{shfl} {p48}, {r0}, {r8}, (?:{i20w8}|{r20}), (?:{i34w13}|{r39});'}],
    'PRMT': [  # prmt
        {'type': x32_t, 'code': 0x36c0000000000000, 'rule': rf'PRMT{prmt} {r0}, {r8}, {i20}, {r39};'},
        {'type': x32_t, 'code': 0x4bc0000000000000, 'rule': rf'PRMT{prmt} {r0}, {r8}, {c20}, {r39};'},
        {'type': x32_t, 'code': 0x5bc0000000000000, 'rule': rf'PRMT{prmt} {r0}, {r8}, {r20}, {r39};'},
        {'type': x32_t, 'code': 0x53c0000000000000, 'rule': rf'PRMT{prmt} {r0}, {r8}, {r39}, {c20};'}],
    'SEL': [  # selp
        {'type': x32_t, 'code': 0x38a0000000000000, 'rule': rf'SEL {r0}, {r8}, {i20}, {p39};'},
        {'type': x32_t, 'code': 0x4ca0000000000000, 'rule': rf'SEL {r0}, {r8}, {c20}, {p39};'},
        {'type': x32_t, 'code': 0x5ca0000000000000, 'rule': rf'SEL {r0}, {r8}, {r20}, {p39};'}],

    # Conversion Instructions
    'F2F': [  # cvt
        {'type': qtr_t, 'code': 0x4ca8000000000000, 'rule': rf'F2F{ftz}{x2x}{rnd}{round_}{sat} {r0}, {c20};'},
        {'type': qtr_t, 'code': 0x5ca8000000000000, 'rule': rf'F2F{ftz}{x2x}{rnd}{round_}{sat} {r0}, {r20};'}],
    'F2I': [  # cvt
        {'type': qtr_t, 'code': 0x4cb0000000000000, 'rule': rf'F2I{ftz}{x2x}{round_} {r0}, {c20};'},
        {'type': qtr_t, 'code': 0x5cb0000000000000, 'rule': rf'F2I{ftz}{x2x}{round_} {r0}, {r20};'}],
    'I2F': [  # cvt
        {'type': qtr_t, 'code': 0x38b8000000000000, 'rule': rf'I2F{x2x}{rnd} {r0}, {i20};'},
        {'type': qtr_t, 'code': 0x4cb8000000000000, 'rule': rf'I2F{x2x}{rnd} {r0}, {c20};'},
        {'type': qtr_t, 'code': 0x5cb8000000000000, 'rule': rf'I2F{x2x}{rnd} {r0}, {r20};'}],
    'I2I': [  # cvt
        {'type': qtr_t, 'code': 0x4ce0000000000000, 'rule': rf'I2I{x2x}{sat} {r0}, {c20};'},
        {'type': qtr_t, 'code': 0x5ce0000000000000, 'rule': rf'I2I{x2x}{sat} {r0}, {r20};'}],

    # Predicate/CC Instructions
    'PSET': [  # set
        {'type': cmp_t, 'code': 0x5088000000000000, 'rule': rf'PSET{bool2}{bool_} {r0}, {p12}, {p29}, {p39};'}],
    'PSETP': [  # setp
        {'type': cmp_t, 'code': 0x5090000000000000, 'rule': rf'PSETP{bool2}{bool_} {p3}, {p0}, {p12}, {p29}, {p39};'}],

    # Compute Load/Store Instructions
    'LD': [  # ld
        {'type': gmem_t, 'code': 0x800000000000ff00, 'rule': rf'LD{mem_cache}{mem_type} {r0}, {addr}, {p58};'}],
    'ST': [  # st
        {'type': gmem_t, 'code': 0xa00000000000ff00, 'rule': rf'ST{mem_cache}{mem_type} {addr}, {r0}, {p58};'}],
    'LDG': [  # ld
        {'type': gmem_t, 'code': 0xeed000000000ff00, 'rule': rf'LDG{mem_cache}{mem_type} {r0}, {addr};'}],
    'STG': [  # st
        {'type': gmem_t, 'code': 0xeed800000000ff00, 'rule': rf'STG{mem_cache}{mem_type} {addr}, {r0};'}],
    'LDS': [  # ld
        {'type': smem_t, 'code': 0xef4800000000ff00, 'rule': rf'LDS{mem_cache}{mem_type} {r0}, {addr};'}],
    'STS': [  # st
        {'type': smem_t, 'code': 0xef5800000000ff00, 'rule': rf'STS{mem_cache}{mem_type} {addr}, {r0};'}],
    'LDL': [  # ld
        {'type': gmem_t, 'code': 0xef4000000000ff00, 'rule': rf'LDL{mem_cache}{mem_type} {r0}, {addr};'}],
    'STL': [  # st
        {'type': gmem_t, 'code': 0xef5000000000ff00, 'rule': rf'STL{mem_cache}{mem_type} {addr}, {r0};'}],
    'LDC': [  # ld
        {'type': gmem_t, 'code': 0xef9000000000ff00, 'rule': rf'LDC{mem_cache}{mem_type} {r0}, {ldc};'}],
    # Note for ATOM(S).CAS operations the last register needs to be in sequence with the second to last
    # (as it's not encoded).
    'ATOM': [  # atom
        {'type': gmem_t, 'code': 0xed0000000000ff00, 'rule': rf'ATOM{atom} {r0}, {addr2}, {r20}(?:, {r39a})?;'}],
    'ATOMS': [  # atom
        {'type': smem_t, 'code': 0xec0000000000ff00, 'rule': rf'ATOMS{atom} {r0}, {addr3}, {r20}(?:, {r39a})?;'}],
    'RED': [  # red
        {'type': gmem_t, 'code': 0xebf800000000ff00, 'rule': rf'RED{atom} {addr2}, {r0};'}],

    # Control Instructions
    'BRA': [  # bra
        {'type': x32_t, 'code': 0xe24000000000000f, 'rule': rf'BRA(?P<U>\.U)? ((?P<CC_NEU>CC.NEU), )?{i20w24};'}],
    'BRX': [  # brx
        {'type': x32_t, 'code': 0xe25000000000000f, 'rule': rf'BRX {r8} {i20w24};'}],
    'PBK': [  # 类似SSY
        {'type': x32_t, 'code': 0xe2a0000000000000, 'rule': rf'{noPred}?PBK {i20w24};'}],
    'BRK': [  # bra
        {'type': x32_t, 'code': 0xe34000000000000f, 'rule': rf'BRK;'}],
    'SSY': [  # 映射label后忽略
        {'type': x32_t, 'code': 0xe290000000000000, 'rule': rf'{noPred}?SSY {i20w24};'}],
    'SYNC': [  # bra
        {'type': x32_t, 'code': 0xf0f800000000000f, 'rule': rf'SYNC;'}],
    'CAL': [  # call
        {'type': x32_t, 'code': 0xe260000000000040, 'rule': rf'{noPred}?CAL {i20w24};'}],
    'RET': [  # ret
        {'type': x32_t, 'code': 0xe32000000000000f, 'rule': rf'RET;'}],
    'EXIT': [  # exit
        {'type': x32_t, 'code': 0xe30000000000000f, 'rule': rf'EXIT;'}],

    # Miscellaneous Instructions
    'NOP': [  # 忽略
        {'type': x32_t, 'code': 0x50b0000000000f00, 'rule': rf'NOP;'}],
    'BAR': [  # bar
        {'type': gmem_t, 'code': 0xf0a80b8000000000, 'rule': rf'BAR\.SYNC (?:{i8w8}|{r8});'}],
    'DEPBAR': [  # bar
        {'type': gmem_t, 'code': 0xf0f0000000000000, 'rule': rf'DEPBAR{icmp} {dbar_sb}, {i20w6}(, {dbar_db})?;'},
        {'type': gmem_t, 'code': 0xf0f0000000000000, 'rule': rf'DEPBAR {dbar_db};'}],
    'MEMBAR': [  # membar
        {'type': x32_t, 'code': 0xef98000000000000, 'rule': rf'MEMBAR{mbar};'}],
    'VOTE': [  # vote
        {'type': vote_t, 'code': 0x50d8000000000000, 'rule': rf'VOTE{vote} {r0}, {p45}, {p39};'},
        {'type': vote_t, 'code': 0x50d8000000000000, 'rule': rf'VOTE{vote} {p45}, {p39};'}],
    'S2R': [  # mov
        {'type': x32_t, 'code': 0xf0c8000000000000, 'rule': rf'S2R {r0}, {sr};'}],
    'R2P': [
        {'type': shft_t, 'code': 0x38f0000000000000, 'rule': rf'R2P {r2p}, {r8}, {i20};'}],
}

# r16 r24 r32 r64
ureg = fr'UR[Z0-9]+'
ur16 = fr'(?P<ur16>{ureg})'
ur24 = fr'(?P<ur24neg>[\-~])?(?P<ur24>{ureg})'
ur32 = fr'(?P<ur32neg>[\-~])?(?P<ur32>{ureg})'
ur64 = fr'(?P<ur64neg>[\-~])?(?P<ur64>{ureg})'
r16 = fr'(?P<r16>{reg})'
r24 = fr'(?P<r24neg>[\-~])?(?P<r24>{reg})(?P<reuse1>\.reuse)?'
r32 = fr'(?P<r32neg>[\-~])?(?P<r32>{reg})(?P<reuse2>\.reuse)?'
r64 = fr'(?P<r64neg>[\-~])?(?P<r64>{reg})(?P<reuse3>\.reuse)?'
# i32
i32 = fr'(?P<i32>(?P<neg>\-)?{immed})'
i32a4 = fr'(?P<i32a4>(?P<neg>\-)?{immed})'
i40w24 = fr'(?P<i40w24>(?P<neg>\-)?{immed})'
i38w16 = fr'(?P<i38w16>(?P<neg>\-)?{immed})'
i38w6 = fr'(?P<i38w6>{immed})'
i40w13 = fr'(?P<i40w13>{immed})'
i72w8 = fr'(?P<i72w8>{immed})'
i72w4 = fr'(?P<i72w4>{immed})'
i75w5 = fr'(?P<i75w5>{immed})'
i54w4 = fr'(?P<i54w4>{immed})'
# c[c54][c40]
c40 = fr'(?P<c40neg>\-)?(?P<c40abs>\|)?c\[((?P<c54>{hexx})|(?P<ur32>{ureg}))\]\s*\[(?P<c40>{hexx})\]\|?'

UP = fr'UP[0-7]'

up77 = fr'(?P<up77not>\!)?(?P<up77>{UP})'
up87 = fr'(?P<up87not>\!)?(?P<up87>{UP})'
up81 = fr'(?P<up81>{UP})'
up84 = fr'(?P<up84>{UP})'

p68 = fr'(?P<p68not>\!)?(?P<p68>{P})'
p77 = fr'(?P<p77not>\!)?(?P<p77>{P})'
p87 = fr'(?P<p87not>\!)?(?P<p87>{P})'
p81 = fr'(?P<p81>{P})'
p84 = fr'(?P<p84>{P})'

p64q = fr'(?P<p64qnot>\!)?(?P<p64>{P})'

addr24 = fr'\[(?:(?P<r24>{reg})(?P<r24x>\.X(4|8|16))?)?(?:\s*\+?\s*{i40w24})?\]'
uaddr32 = fr'\[(?:(?P<r24>{reg})(?P<r24x>\.X(4|8|16))?(?P<r24type>\.64|\.U32)?)?' \
          rf'(?:\s*\+?\s*(?P<ur32>{ureg}))?(?:\s*\+?\s*{i40w24})?\]'
uaddr64 = fr'\[(?:(?P<r24>{reg})(?P<r24type>\.64|\.U32)?)?(?:\s*\+?\s*(?P<ur64>{ureg}))?(?:\s*\+?\s*{i40w24})?\]'
tldc = rf'c\[(?P<c54>{hexx})\]\s*\[(?P<r24>{reg})?(?:\s*\+?\s*{i38w16})?\]'

b16 = rf'(?P<b16>B\d+)'
b24w5 = rf'(?P<b24w5>\S+?)'

# flags
timad = rf'((\.IADD|\.SHL|\.MOV)|(?P<wide>\.WIDE))?'

te = fr'(?P<E>\.E)?'
tu = fr'(?P<U>\.U)?'
tmem_ltc = fr'(?P<ltc>\.LTC(64|128)B)?'
tmem_type = fr'(?P<type>\.U8|\.S8|\.U16|\.S16|\.64|\.128|\.U\.128)?'
tmem_cache = fr'(?P<cache>\.EF|\.EL|\.LU|\.EU|\.NA)?'
tmem_scope = fr'(?P<scope>\.CTA|\.SM|\.GPU|\.SYS)?'
tmem_const = fr'(?P<const>\.CONSTANT|\.STRONG|\.MMIO)?'

tprivate = rf'(?P<PRIVATE>\.PRIVATE)?'
tzd = rf'(?P<ZD>\.ZD)?'

tbmov = rf'\.32(?P<CLEAR>\.CLEAR)?'

ticmp = fr'(?P<cmp>\.F|\.LT|\.EQ|\.LE|\.GT|\.NE|\.GE|\.T)'
tbool = fr'(?P<bool>\.AND|\.OR|\.XOR)'
tex = fr'(?P<EX>\.EX)?'

tvote = fr'(?P<vote>\.ALL|\.ANY|\.EQ)'
tsh = fr'(?P<SH>\.SH)?'

tatom_type = fr'(?P<type>\.S32|\.F32\.FTZ\.RN|\.F16x2\.RN|\.S64|\.64|\.F64\.RN)?'
tatom_op = fr'(?P<op>\.ADD|\.MIN|\.MAX|\.INC|\.DEC|\.AND|\.OR|\.XOR|\.EXCH|\.SAFEADD)'

tpand = rf'(?P<PAND>\.PAND)?'

thi = rf'(?P<HI>\.HI)?'
tw = fr'(?P<W>\.W)?'
tshf_lr = rf'(?P<lr>\.L|\.R)'
tshf_type = rf'(?P<type>\.S64|\.U64|\.S32|\.U32){thi}'

tldc_isl = rf'(?P<isl>\.IL|\.IS|\.ISL)?'

tcs2r = rf'(?P<type>\.32)?'

tnoinc = rf'(?P<NOINC>\.NOINC)?'
tnodec = rf'(?P<NODEC>\.NODEC)?'
tra = rf'(?P<type>\.REL|\.ABS)'

tsx32 = rf'(?P<SX32>\.SX32)?'

tprmt = rf'(?P<prmt>\.F4E|\.B4E|\.RC8|\.ECL|\.ECR|\.RC16)?'

tp2r = rf'(?P<B>\.B1|\.B2|\.B3)?'

tle = rf'(?P<LE>\.LE)?'
tdbar_db = r'(\{(?P<db>[0-5])\})'

grammar_75 = {
    'IMAD': [
        {'type': 'x32', 'code': 0x224,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {r32}, {r64}(, {p87})?;'},
        {'type': 'x32', 'code': 0x424,
         'rule': rf'IMAD(\.MOV)?{u32}{X} {r16}, ({p81}, )?{r24}, {r64}, {i32}(, {p87})?;'},
        {'type': 'x32', 'code': 0x624,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {r64}, {c40}(, {p87})?;'},
        {'type': 'x32', 'code': 0x824,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {i32}, {r64}(, {p87})?;'},
        {'type': 'x32', 'code': 0xa24,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {c40}, {r64}(, {p87})?;'},
        {'type': 'x32', 'code': 0xc24,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {ur32}, {r64}(, {p87})?;'},
        {'type': 'x32', 'code': 0xe24,
         'rule': rf'IMAD{timad}{u32}{X} {r16}, ({p81}, )?{r24}, {r64}, {ur32}(, {p87})?;'},
    ],
    'UIMAD': [
        {'type': 'x32', 'code': 0x2a4,
         'rule': rf'IMAD{timad}{u32}{X} {ur16}, ({up81}, )?{ur24}, {ur32}, {ur64}(, {up87})?;'},
    ],
    'S2R': [
        {'type': 'x32', 'code': 0x919, 'rule': rf'S2R {r16}, {sr};'},
    ],
    'S2UR': [
        {'type': 'x32', 'code': 0x9c3, 'rule': rf'S2UR {ur16}, {sr};'},
    ],
    'CS2R': [
        {'type': 'x32', 'code': 0x805, 'rule': rf'CS2R{tcs2r} {r16}, {sr};'},
    ],
    'LDG': [
        {'type': 'x32', 'code': 0x381,
         'rule': rf'LDG{te}{tmem_cache}{tmem_ltc}{tmem_type}{tmem_const}{tmem_scope}{tprivate}{tzd}'
                 rf' ({p81}, )?{r16}, {addr24}(, {p64q})?;'},
        {'type': 'x32', 'code': 0x981,
         'rule': rf'LDG{te}{tmem_cache}{tmem_ltc}{tmem_type}{tmem_const}{tmem_scope}{tprivate}{tzd}'
                 rf' ({p81}, )?{r16}, {uaddr32}(, {p64q})?;'},
    ],
    'STG': [
        {'type': 'x32', 'code': 0x386,
         'rule': rf'STG{te}{tmem_cache}{tmem_type}{tmem_const}{tmem_scope}{tprivate}{tzd}'
                 rf' {addr24}, {r32};'},
        {'type': 'x32', 'code': 0x986,
         'rule': rf'STG{te}{tmem_cache}{tmem_type}{tmem_const}{tmem_scope}{tprivate}{tzd}'
                 rf' {uaddr64}, {r32};'},
    ],
    'LDS': [
        {'type': 'x32', 'code': 0x984,
         'rule': rf'LDS{tu}{tmem_type}{tzd} {r16}, {uaddr32};'},
    ],
    'STS': [
        {'type': 'x32', 'code': 0x388,
         'rule': rf'STS{tmem_type} {addr24}, {r32};'},
    ],
    'ATOMS': [
        {'type': 'x32', 'code': 0x38c,
         'rule': rf'ATOMS{tatom_op}{tmem_type} {r16}, {addr24}, {r32}(, {r64})?;'},
    ],
    'ATOMG': [
        {'type': 'x32', 'code': 0x3a8,
         'rule': rf'ATOMG{te}{tatom_op}{tmem_cache}{tmem_type}{tmem_const}{tmem_scope}{tprivate}'
                 rf' ({p81}, )?{r16}, {addr24}, {r32}(, {r64})?;'},
        {'type': 'x32', 'code': 0x9a8,
         'rule': rf'ATOMG{te}{tatom_op}{tmem_cache}{tmem_type}{tmem_const}{tmem_scope}{tprivate}'
                 rf' ({p81}, )?{r16}, {uaddr64}, {r32};'},
    ],
    'LDC': [
        {'type': 'x32', 'code': 0xb82,
         'rule': rf'LDC{tmem_type}{tldc_isl} {r16}, {tldc};'},
    ],
    'ULDC': [
        {'type': 'x32', 'code': 0xab9,
         'rule': rf'ULDC{tmem_type} {ur16}, {c40};'},
    ],
    'BMOV': [
        {'type': 'x32', 'code': 0x355, 'rule': rf'BMOV{tbmov} {r16}, {b24w5};'},
    ],
    'BSSY': [
        {'type': 'x32', 'code': 0x945, 'rule': rf'BSSY ({p87}, )?{b16}, {i32a4};'},
    ],
    'BSYNC': [
        {'type': 'x32', 'code': 0x941, 'rule': rf'BSYNC ({p87}, )?{b16};'},
    ],
    'WARPSYNC': [
        {'type': 'x32', 'code': 0x948, 'rule': rf'WARPSYNC ({p87}, )?{i32};'},
    ],
    'BAR': [
        {'type': 'x32', 'code': 0xb1d, 'rule': rf'BAR\.SYNC {i54w4};'}],
    'BRA': [
        {'type': 'x32', 'code': 0x947, 'rule': rf'BRA ({p87}, )?{i32a4};'},
    ],
    'EXIT': [
        {'type': 'x32', 'code': 0x94d, 'rule': rf'EXIT( {p87}, )?;'}],
    'LOP3': [
        {'type': 'x32', 'code': 0x212,
         'rule': rf'LOP3\.LUT{tpand} ({p81}, )?{r16}, {r24}, {r32}, {r64}, {i72w8}, {p87};'},
        {'type': 'x32', 'code': 0x812,
         'rule': rf'LOP3\.LUT{tpand} ({p81}, )?{r16}, {r24}, {i32}, {r64}, {i72w8}, {p87};'},
        {'type': 'x32', 'code': 0xa12,
         'rule': rf'LOP3\.LUT{tpand} ({p81}, )?{r16}, {r24}, {c40}, {r64}, {i72w8}, {p87};'},
        {'type': 'x32', 'code': 0xc12,
         'rule': rf'LOP3\.LUT{tpand} ({p81}, )?{r16}, {r24}, {ur32}, {r64}, {i72w8}, {p87};'},
    ],
    'ISETP': [
        {'type': 'x32', 'code': 0x20c,
         'rule': rf'ISETP{ticmp}{u32}{tbool}{tex} {p81}, {p84}, {r24}, {r32}, {p87}(, {p68})?;'},
        {'type': 'x32', 'code': 0x80c,
         'rule': rf'ISETP{ticmp}{u32}{tbool}{tex} {p81}, {p84}, {r24}, {i32}, {p87}(, {p68})?;'},
        {'type': 'x32', 'code': 0xc0c,
         'rule': rf'ISETP{ticmp}{u32}{tbool}{tex} {p81}, {p84}, {r24}, {ur32}, {p87}(, {p68})?;'},
    ],
    'IMNMX': [
        {'type': 'x32', 'code': 0x817, 'rule': rf'IMNMX{u32} {r16}, {r24}, {i32}, {p87};'},
    ],
    'MOV': [
        {'type': 'x32', 'code': 0x802, 'rule': rf'MOV {r16}, {i32}(, {i72w4})?;'},
        {'type': 'x32', 'code': 0xc02, 'rule': rf'MOV {r16}, {ur32}(, {i72w4})?;'},
    ],
    'UMOV': [
        {'type': 'x32', 'code': 0x882, 'rule': rf'UMOV {ur16}, {i32};'},
    ],
    'P2R': [
        {'type': 'x32', 'code': 0x803, 'rule': rf'P2R{tp2r} {r16}, PR, {r24}, {i32};'},
    ],
    'IADD3': [
        {'type': 'x32', 'code': 0x210,
         'rule': rf'IADD3{X} {r16}, ({p81}, )?({p84}, )?{r24}, {r32}, {r64}(, {p87})?(, {p77})?;'},
        {'type': 'x32', 'code': 0x810,
         'rule': rf'IADD3{X} {r16}, ({p81}, )?({p84}, )?{r24}, {i32}, {r64}(, {p87})?(, {p77})?;'},
        {'type': 'x32', 'code': 0xa10,
         'rule': rf'IADD3{X} {r16}, ({p81}, )?({p84}, )?{r24}, {c40}, {r64}(, {p87})?(, {p77})?;'},
        {'type': 'x32', 'code': 0xc10,
         'rule': rf'IADD3{X} {r16}, ({p81}, )?({p84}, )?{r24}, {ur32}, {r64}(, {p87})?(, {p77})?;'},
    ],
    'UIADD3': [
        {'type': 'x32', 'code': 0x290,
         'rule': rf'UIADD3{X} {ur16}, ({up81}, )?({up84}, )?{ur24}, {ur32}, {ur64}(, {up87})?(, {up77})?;'},
        {'type': 'x32', 'code': 0x890,
         'rule': rf'UIADD3{X} {ur16}, ({up81}, )?({up84}, )?{ur24}, {i32}, {ur64}(, {up87})?(, {up77})?;'},
    ],
    'VOTE': [
        {'type': 'x32', 'code': 0x806, 'rule': rf'VOTE{tvote} {r16}, {p81}, {p87};'},
    ],
    'VOTEU': [
        {'type': 'x32', 'code': 0x886, 'rule': rf'VOTEU{tvote} {ur16}, {up81}, {p87};'},
    ],
    'FLO': [
        {'type': 'x32', 'code': 0x300, 'rule': rf'FLO{u32}{tsh} {r16}, ({p81}, )?{r32};'},
        {'type': 'x32', 'code': 0xd00, 'rule': rf'FLO{u32}{tsh} {r16}, ({p81}, )?{ur32};'},
    ],
    'POPC': [
        {'type': 'x32', 'code': 0x309, 'rule': rf'POPC {r16}, {r32};'},
        {'type': 'x32', 'code': 0xd09, 'rule': rf'POPC {r16}, {ur32};'},
    ],
    'UPOPC': [
        {'type': 'x32', 'code': 0x2bf, 'rule': rf'UPOPC {ur16}, {ur32};'},
    ],
    'SHFL': [
        {'type': 'x32', 'code': 0x389, 'rule': rf'SHFL{shfl} {p81}, {r16}, {r24}, {r32}, {r64};'},
        {'type': 'x32', 'code': 0x589, 'rule': rf'SHFL{shfl} {p81}, {r16}, {r24}, {r32}, {i40w13};'},
    ],
    'SHF': [
        {'type': 'x32', 'code': 0x219, 'rule': rf'SHF{tshf_lr}{tw}{tshf_type} {r16}, {r24}, {r32}, {r64};'},
        {'type': 'x32', 'code': 0x819, 'rule': rf'SHF{tshf_lr}{tw}{tshf_type} {r16}, {r24}, {i32}, {r64};'},
    ],
    'USHF': [
        {'type': 'x32', 'code': 0x899, 'rule': rf'USHF{tshf_lr}{tw}{tshf_type} {ur16}, {ur24}, {i32}, {ur64};'},
    ],
    'SGXT': [
        {'type': 'x32', 'code': 0x81a, 'rule': rf'SGXT{tw}{u32} {r16}, {r24}, {i32};'},
    ],
    'SEL': [
        {'type': 'x32', 'code': 0x207, 'rule': rf'SEL {r16}, {r24}, {r32}, {p87};'},
        {'type': 'x32', 'code': 0x807, 'rule': rf'SEL {r16}, {r24}, {i32}, {p87};'},
    ],
    'LEA': [
        {'type': 'x32', 'code': 0x211,
         'rule': rf'LEA{thi}{X}{tsx32} {r16}, ({p81}, )?{r24}, {r32}, ({r64}, )?{i75w5}(, {p87})?;'},
        {'type': 'x32', 'code': 0x811,
         'rule': rf'LEA{thi}{X}{tsx32} {r16}, ({p81}, )?{r24}, {i32}, ({r64}, )?{i75w5}(, {p87})?;'},
        {'type': 'x32', 'code': 0xa11,
         'rule': rf'LEA{thi}{X}{tsx32} {r16}, ({p81}, )?{r24}, {c40}, ({r64}, )?{i75w5}(, {p87})?;'},
        {'type': 'x32', 'code': 0xc11,
         'rule': rf'LEA{thi}{X}{tsx32} {r16}, ({p81}, )?{r24}, {ur32}, ({r64}, )?{i75w5}(, {p87})?;'},
    ],
    'NOP': [
        {'type': 'x32', 'code': 0x918, 'rule': rf'NOP;'},
    ],
    'YIELD': [
        {'type': 'x32', 'code': 0x946, 'rule': rf'YIELD( {p87})?;'},
    ],
    'CALL': [
        {'type': 'x32', 'code': 0x944, 'rule': rf'CALL\.REL{tnoinc}( {p87},)? {i32a4};'},
    ],
    'RET': [
        {'type': 'x32', 'code': 0x950, 'rule': rf'RET{tra}{tnodec}( {p87},)? {r24} {i32a4};'},
    ],
    'DEPBAR': [
        {'type': 'x32', 'code': 0x91a, 'rule': rf'DEPBAR{tle} {dbar_sb}, {i38w6}(, {dbar_db})?;'},
    ],
    'PRMT': [
        {'type': 'x32', 'code': 0x216, 'rule': rf'PRMT{tprmt} {r16}, {r24}, {r32}, {r64};'},
        {'type': 'x32', 'code': 0x816, 'rule': rf'PRMT{tprmt} {r16}, {r24}, {i32}, {r64};'},
    ],
}

flags_str_61 = '''
MEMBAR: mode
0x0000000000000000 CTA
0x0000000000000100 GL
0x0000000000000200 SYS

DEPBAR: SB
0x0000000000000000 SB0
0x0000000004000000 SB1
0x0000000008000000 SB2
0x000000000c000000 SB3
0x0000000010000000 SB4
0x0000000014000000 SB5

DEPBAR: cmp
0x0000000020000000 LE

DEPBAR: db0
0x0000000000000001 0

DEPBAR: db1
0x0000000000000002 1

DEPBAR: db2
0x0000000000000004 2

DEPBAR: db3
0x0000000000000008 3

DEPBAR: db4
0x0000000000000010 4

DEPBAR: db5
0x0000000000000020 5

MUFU: r8neg
0x0001000000000000 -

MUFU: func
0x0000000000000000 COS
0x0000000000100000 SIN
0x0000000000200000 EX2
0x0000000000300000 LG2
0x0000000000400000 RCP
0x0000000000500000 RSQ
0x0000000000600000 RCP64H
0x0000000000700000 RSQ64H

FLO, IMNMX, SEL, BFI, ICMP, BFE, ISCADD, SHL, SHR, LEA, SHF, IADD, IADD3, ISET, ISETP, LOP, MOV, XMAD, LOP3: neg
0x0100000000000000 -

LEA: neg37
0x0000001000000000 -

LEA: neg45
0x0000100000000000 -

PSET, PSETP: p12not
0x0000000000008000 !

PSET, PSETP: p29not
0x0000000100000000 !

# FMNMX, FSET, FSETP, DMNMX, DSET, DSETP, IMNMX, ISET, ISETP, SEL, PSET, PSETP, BAR, VOTE
VOTE, IMNMX, PSET, PSETP, SEL, ISET, ISETP: p39not
0x0000040000000000 !

VOTE: mode
0x0000000000000000 ALL
0x0001000000000000 ANY
0x0002000000000000 EQ

LEA: X
0x0200000000000000 .X

LEA: X46
0x0000400000000000 .X

LEA: X38
0x0000004000000000 .X

# IADD, IADD3, XMAD, LEA, IMNMX
ISET, ISCADD, F2F, LEA, IADD, IADD3, XMAD: CC
0x0000800000000000 .CC

IADD3: type
0x0001000000000000 X
0x0000002000000000 RS
0x0000004000000000 LS

IADD3: r8part
0x0000000000000000 H0
0x0000001000000000 H1

IADD3: r20part, i20part, c20part
0x0000000080000000 H0

IADD3: r39part
0x0000000200000000 H0

IADD3: r8neg
0x0008000000000000 -

IADD3: r20neg, i20neg, c20neg
0x0004000000000000 -

IADD3: r39neg
0x0002000000000000 -

IADD32I: CC
0x0010000000000000 .CC

SHF: W
0x0004000000000000 .W

SHF: HI
0x0001000000000000 .HI

SHF: type
0x0000004000000000 U64
0x0000006000000000 S64

PRMT: mode
0x0001000000000000 F4E
0x0002000000000000 B4E
0x0003000000000000 RC8
0x0004000000000000 ECL
0x0005000000000000 ECR
0x0006000000000000 RC16

XMAD: type1
0x0000000000000000 U16
0x0001000000000000 S16

XMAD: type2
0x0000000000000000 U16
0x0002000000000000 S16

XMAD: mode
0x0000002000000000 MRG
0x0000001000000000 PSL
0x0008000000000000 CHI
0x0004000000000000 CLO
0x000c000000000000 CSFU
0x0004001000000000 PSL.CLO
0x0008001000000000 PSL.CHI

XMAD: modec
0x0004000000000000 CLO
0x0008000000000000 CHI
0x000c000000000000 CSFU
0x0040000000000000 X
0x0080000000000000 PSL
0x0100000000000000 MRG
0x0084000000000000 PSL.CLO

XMAD: CBCC
0x0010000000000000 .CBCC

XMAD: r8part
0x0000000000000000 H0
0x0020000000000000 H1

XMAD: r20part
0x0000000000000000 H0
0x0000000800000000 H1

XMAD: c20part
0x0000000000000000 H0
0x0010000000000000 H1

XMAD: r39part
0x0000000000000000 H0
0x0010000000000000 H1

SHL: W
0x0000008000000000 .W

IMNMX, ICMP, BFE, SHR, ISET, ISETP: U32
0x0001000000000000 .U32

SHFL: mode
0x0000000000000000 IDX
0x0000000040000000 UP
0x0000000080000000 DOWN
0x00000000c0000000 BFLY

ICMP, ISET, ISETP: cmp
0x0002000000000000 LT
0x0004000000000000 EQ
0x0006000000000000 LE
0x0008000000000000 GT
0x000a000000000000 NE
0x000c000000000000 GE

ISET, ISETP, PSET, PSETP: bool
0x0000000000000000 AND
0x0000200000000000 OR
0x0000400000000000 XOR

PSET, PSETP: bool2
0x0000000000000000 AND
0x0000000001000000 OR
0x0000000002000000 XOR

LOP, IADD, ISET, ISETP: X
0x0000080000000000 .X

IADD32I: X
0x0020000000000000 .X

IADD32I: r8neg
0x0100000000000000 -

ISCADD, IADD: r20neg, c20neg
0x0001000000000000 -

ISCADD, IADD: r8neg
0x0002000000000000 -

IADD: SAT
0x0004000000000000 .SAT

LOP: bool
0x0000000000000000 AND
0x0000020000000000 OR
0x0000040000000000 XOR
0x0000060000000000 PASS_B

LOP: INV
0x0000010000000000 ~

LOP: INV8
0x0000008000000000 ~

LOP32I: INV8
0x0080000000000000 ~

LOP: TINV
0x0000010000000000 .INV

LOP: z
0x0000200000000000 Z
0x0000300000000000 NZ

LOP32I: bool
0x0000000000000000 AND
0x0020000000000000 OR
0x0040000000000000 XOR

S2R: sr
0x0000000000000000 SR_LANEID
0x0000000000100000 SR_CLOCK
0x0000000000200000 SR_VIRTCFG
0x0000000000300000 SR_VIRTID
0x0000000000400000 SR_PM0
0x0000000000500000 SR_PM1
0x0000000000600000 SR_PM2
0x0000000000700000 SR_PM3
0x0000000000800000 SR_PM4
0x0000000000900000 SR_PM5
0x0000000000a00000 SR_PM6
0x0000000000b00000 SR_PM7
0x0000000000f00000 SR_ORDERING_TICKET
0x0000000001000000 SR_PRIM_TYPE
0x0000000001100000 SR_INVOCATION_ID
0x0000000001200000 SR_Y_DIRECTION
0x0000000001300000 SR_THREAD_KILL
0x0000000001400000 SM_SHADER_TYPE
0x0000000001500000 SR_DIRECTCBEWRITEADDRESSLOW
0x0000000001600000 SR_DIRECTCBEWRITEADDRESSHIGH
0x0000000001700000 SR_DIRECTCBEWRITEENABLED
0x0000000001800000 SR_MACHINE_ID_0
0x0000000001900000 SR_MACHINE_ID_1
0x0000000001a00000 SR_MACHINE_ID_2
0x0000000001b00000 SR_MACHINE_ID_3
0x0000000001c00000 SR_AFFINITY
0x0000000001d00000 SR_INVOCATION_INFO
0x0000000001e00000 SR_WSCALEFACTOR_XY
0x0000000001f00000 SR_WSCALEFACTOR_Z
0x0000000002000000 SR_TID
0x0000000002100000 SR_TID.X
0x0000000002200000 SR_TID.Y
0x0000000002300000 SR_TID.Z
0x0000000002400000 SR_CTA_PARAM.X
0x0000000002500000 SR_CTAID.X
0x0000000002600000 SR_CTAID.Y
0x0000000002700000 SR_CTAID.Z
0x0000000002800000 SR_NTID
0x0000000002900000 SR_CirQueueIncrMinusOne
0x0000000002a00000 SR_NLATC
0x0000000002c00000 SR_SM_SPA_VERSION
0x0000000002d00000 SR_MULTIPASSSHADERINFO
0x0000000002e00000 SR_LWINHI
0x0000000002f00000 SR_SWINHI
0x0000000003000000 SR_SWINLO
0x0000000003100000 SR_SWINSZ
0x0000000003200000 SR_SMEMSZ
0x0000000003300000 SR_SMEMBANKS
0x0000000003400000 SR_LWINLO
0x0000000003500000 SR_LWINSZ
0x0000000003600000 SR_LMEMLOSZ
0x0000000003700000 SR_LMEMHIOFF
0x0000000003800000 SR_EQMASK
0x0000000003900000 SR_LTMASK
0x0000000003a00000 SR_LEMASK
0x0000000003b00000 SR_GTMASK
0x0000000003c00000 SR_GEMASK
0x0000000003d00000 SR_REGALLOC
0x0000000003e00000 SR_BARRIERALLOC
0x0000000004000000 SR_GLOBALERRORSTATUS
0x0000000004200000 SR_WARPERRORSTATUS
0x0000000004300000 SR_WARPERRORSTATUSCLEAR
0x0000000004800000 SR_PM_HI0
0x0000000004900000 SR_PM_HI1
0x0000000004a00000 SR_PM_HI2
0x0000000004b00000 SR_PM_HI3
0x0000000004c00000 SR_PM_HI4
0x0000000004d00000 SR_PM_HI5
0x0000000004e00000 SR_PM_HI6
0x0000000004f00000 SR_PM_HI7
0x0000000005000000 SR_CLOCKLO
0x0000000005100000 SR_CLOCKHI
0x0000000005200000 SR_GLOBALTIMERLO
0x0000000005300000 SR_GLOBALTIMERHI
0x0000000006000000 SR_HWTASKID
0x0000000006100000 SR_CIRCULARQUEUEENTRYINDEX
0x0000000006200000 SR_CIRCULARQUEUEENTRYADDRESSLOW
0x0000000006300000 SR_CIRCULARQUEUEENTRYADDRESSHIGH

BRA: U
0x0000000000000080 .U

BRA: CC_NEU
0x0000000000000002 CC.NEU

ATOM: type
0x0000000000000000 DEFAULT
0x0002000000000000 .S32
0x0004000000000000 .U64
0x0006000000000000 .F32.FTZ.RN
0x0008000000000000 .F16x2.FTZ.RN
0x000a000000000000 .S64
0x0002000000000000 .64

RED: type
0x0000000000000000 DEFAULT
0x0000000000100000 .S32
0x0000000000200000 .U64
0x0000000000300000 .F32.FTZ.RN
0x0000000000400000 .F16x2.RN
0x0000000000500000 .S64
0x0000000000600000 .F64.RN

RED: mode
0x0000000000000000 ADD
0x0000000000800000 MIN
0x0000000001000000 MAX
0x0000000001800000 INC
0x0000000002000000 DEC
0x0000000002800000 AND
0x0000000003000000 OR
0x0000000003800000 XOR

ATOM, RED: E
0x0001000000000000 .E

ATOM: mode
0x0000000000000000 ADD
0x0010000000000000 MIN
0x0020000000000000 MAX
0x0030000000000000 INC
0x0040000000000000 DEC
0x0050000000000000 AND
0x0060000000000000 OR
0x0070000000000000 XOR
0x0080000000000000 EXCH
0x03f0000000000000 CAS

ATOMS: type
0x0000000000000000 DEFAULT
0x0000000010000000 .S32
0x0000000020000000 .U64
0x0000000030000000 .S64
0x0010000000000000 .64

ATOMS: mode
0x0000000000000000 ADD
0x0010000000000000 MIN
0x0020000000000000 MAX
0x0030000000000000 INC
0x0040000000000000 DEC
0x0050000000000000 AND
0x0060000000000000 OR
0x0070000000000000 XOR
0x0080000000000000 EXCH
0x0240000000000000 CAS

LDG, STG, LDS, STS, LDL, STL, LDC: type
0x0000000000000000 U8
0x0001000000000000 S8
0x0002000000000000 U16
0x0003000000000000 S16
0x0004000000000000 DEFAULT
0x0004000000000000 32
0x0005000000000000 64
0x0006000000000000 128

LD, ST: type
0x0000000000000000 U8
0x0020000000000000 S8
0x0040000000000000 U16
0x0060000000000000 S16
0x0080000000000000 DEFAULT
0x0080000000000000 32
0x00a0000000000000 64
0x00c0000000000000 128

LD, ST: cache
0x0100000000000000 CG
0x0200000000000000 CS
0x0300000000000000 CV
0x0300000000000000 WT

LD, ST: E
0x0010000000000000 .E

LDG, STG: cache
0x0000400000000000 CG
0x0000800000000000 CI
0x0000800000000000 CS
0x0000c00000000000 CV
0x0000c00000000000 WT

LDL: cache
0x0000200000000000 CI
0x0000100000000000 LU

LDC: cache
0x0000100000000000 IL

LDG, STG, LDS, STS, LDL, STL, LDC: E
0x0000200000000000 .E

LDG: U
0x0001000000000000 .U

LDS: U
0x0000100000000000 .U

F2F, F2I, I2F, I2I: destWidth
0x0000000000000000 8
0x0000000000000100 16
0x0000000000000200 32
0x0000000000000300 64

F2F, F2I, I2F, I2I: srcWidth
0x0000000000000000 8
0x0000000000000400 16
0x0000000000000800 32
0x0000000000000c00 64

F2F, F2I, I2F, I2I: destSign
0x0000000000000000 F
0x0000000000000000 U
0x0000000000001000 S

F2F, F2I, I2F, I2I: srcSign
0x0000000000000000 F
0x0000000000000000 U
0x0000000000002000 S

F2I, I2F, I2I: r20part, c20part
0x0000000000000000 H0
0x0000040000000000 H1
0x0000000000000000 B0
0x0000020000000000 B1
0x0000040000000000 B2
0x0000060000000000 B3

F2F: r20part, c20part
0x0000000000000000 H0
0x0000020000000000 H1

F2F: round
0x0000040000000000 ROUND
0x0000048000000000 FLOOR
0x0000050000000000 CEIL
0x0000058000000000 TRUNC

F2I: round
0x0000000000000000 ROUND
0x0000008000000000 FLOOR
0x0000010000000000 CEIL
0x0000018000000000 TRUNC

F2F, I2F: rnd
0x0000000000000000 RN
0x0000008000000000 RM
0x0000010000000000 RP
0x0000018000000000 RZ

F2F, F2I: FTZ
0x0000100000000000 .FTZ

F2F, I2I: SAT
0x0004000000000000 .SAT

F2F, F2I, I2F, I2I: r20neg, c20neg
0x0000200000000000 -

F2F, F2I, I2F, I2I: r20abs, c20abs
0x0002000000000000 |

IDP: mode
0x0000000000000000 4A
0x0001000000000000 2A

IDP: part
0x0000000000000000 .LO
0x0004000000000000 .HI

IDP: type1
0x0000000000000000 U8
0x0000000000000000 U16
0x0002000000000000 S8
0x0002000000000000 S16

IDP: type2
0x0000000000000000 U8
0x0000800000000000 S8

R2P: r2p
0x0000000000000000 PR
0x0000010000000000 CC

R2P: r8part
0x0000020000000000 B1
0x0000040000000000 B2
0x0000060000000000 B3
'''

flags_str_75 = '''
DEPBAR: LE
0x00000000000000000000800000000000 .LE

DEPBAR: SB
0x00000000000000000000000000000000 SB0
0x00000000000000000000100000000000 SB1
0x00000000000000000000200000000000 SB2
0x00000000000000000000300000000000 SB3
0x00000000000000000000400000000000 SB4
0x00000000000000000000500000000000 SB5

DEPBAR: DB
0x00000000000000000000000100000000 0
0x00000000000000000000000200000000 1
0x00000000000000000000000400000000 2
0x00000000000000000000000800000000 3
0x00000000000000000000001000000000 4
0x00000000000000000000002000000000 5

P2R: B
0x00000000000010000000000000000000 .B1
0x00000000000020000000000000000000 .B2
0x00000000000030000000000000000000 .B3

LEA: r24neg
0x00000000000001000000000000000000 -
0x00000000000001000000000000000000 ~

LEA: r32neg
0x00000000000000008000000000000000 -
0x00000000000000008000000000000000 ~

PRMT: prmt
0x00000000000001000000000000000000 .F4E
0x00000000000002000000000000000000 .B4E
0x00000000000003000000000000000000 .RC8
0x00000000000004000000000000000000 .ECL
0x00000000000005000000000000000000 .ECR
0x00000000000006000000000000000000 .RC16

CALL: NOINC
0x00000000004000000000000000000000 .NOINC

RET: NODEC
0x00000000004000000000000000000000 .NODEC

RET: type
0x00000000000000000000000000000000 .REL
0x00000000002000000000000000000000 .ABS

STS, LDS, ATOMS: r24x
0x00000000000040000000000000000000 .X4
0x00000000000080000000000000000000 .X8
0x000000000000c0000000000000000000 .X16

MOV: i72w4
0x0000000000000f000000000000000000 DEFAULT

LEA: SX32
0x00000000000002000000000000000000 .SX32

LEA, ATOMS, ATOMG: r64
0x00000000000000ff0000000000000000 DEFAULT

SHF, USHF: type
0x00000000000000000000000000000000 .S64
0x00000000000002000000000000000000 .U64
0x00000000000004000000000000000000 .S32
0x00000000000006000000000000000000 .U32

SHF, USHF, LEA: HI
0x00000000000100000000000000000000 .HI

SHF, USHF, SGXT: W
0x00000000000008000000000000000000 .W

SHF, USHF: lr
0x00000000000000000000000000000000 .L
0x00000000000010000000000000000000 .R

SHFL: mode
0x00000000000000000000000000000000 .IDX
0x00000000000000000400000000000000 .UP
0x00000000000000000800000000000000 .DOWN
0x00000000000000000c00000000000000 .BFLY

FLO: SH
0x00000000000004000000000000000000 .SH

VOTE, VOTEU: vote
0x00000000000000000000000000000000 .ALL
0x00000000000001000000000000000000 .ANY
0x00000000000002000000000000000000 .EQ

ISETP: cmp
0x00000000000000000000000000000000 .F
0x00000000000010000000000000000000 .LT
0x00000000000020000000000000000000 .EQ
0x00000000000030000000000000000000 .LE
0x00000000000040000000000000000000 .GT
0x00000000000050000000000000000000 .NE
0x00000000000060000000000000000000 .GE
0x00000000000070000000000000000000 .T

ISETP: bool
0x00000000000000000000000000000000 .AND
0x00000000000004000000000000000000 .OR
0x00000000000008000000000000000000 .XOR

ISETP: EX
0x00000000000001000000000000000000 .EX

ISETP: p68not
0x00000000000000800000000000000000 !

ISETP: p68
0x00000000000000700000000000000000 DEFAULT

IMAD, UIMAD: wide
0x00000000000000000000000000000001 .WIDE

IMAD, UIMAD, ISETP, IMNMX, FLO, SGXT: U32
0x00000000000000000000000000000000 .U32
0x00000000000002000000000000000000 DEFAULT

IMAD, UIMAD, UIADD3, IADD3, LEA: X
0x00000000000004000000000000000000 .X

IMAD, IADD3: r64neg
0x00000000000008000000000000000000 -
0x00000000000008000000000000000000 ~

UIADD3: ur24neg
0x00000000000001000000000000000000 -
0x00000000000001000000000000000000 ~

IADD3, LEA: r24neg
0x00000000000001000000000000000000 -
0x00000000000001000000000000000000 ~

IADD3, UIADD3, FLO, UPOPC, POPC: ur32neg
0x00000000000000008000000000000000 -
0x00000000000000008000000000000000 ~

POPC, FLO: r32neg
0x00000000000000008000000000000000 -
0x00000000000000008000000000000000 ~

UIMAD, UIADD3: ur64neg
0x00000000000008000000000000000000 -
0x00000000000008000000000000000000 ~

IMAD, UIMAD, LEA, IADD3: c40neg
0x00000000000000008000000000000000 -

IMAD, IADD3, LEA: p87
0x00000000078000000000000000000000 DEFAULT

UIMAD, UIADD3: up87
0x00000000078000000000000000000000 DEFAULT

UIADD3: up77
0x000000000001e0000000000000000000 DEFAULT

UIADD3, UIMAD: up81
0x00000000000e00000000000000000000 DEFAULT

UIADD3: up84
0x00000000007000000000000000000000 DEFAULT

IADD3: p77
0x000000000001e0000000000000000000 DEFAULT

IADD3: p84
0x00000000007000000000000000000000 DEFAULT

IMAD, UIMAD, LOP3, ISETP, IMNMX, SEL, WARPSYNC: p87not
0x00000000040000000000000000000000 !

IADD3: p77not
0x00000000000100000000000000000000 !

LDG, LDS, IMAD, UIMAD, ULDC, IADD3, FLO, POPC, UPOPC, LOP3, LEA, ISETP, MOV: ur32
0x00000000080000000000000000000000 ALL

IMAD, IADD3, LEA, LDG, FLO, LOP3: p81
0x00000000000e00000000000000000000 DEFAULT

LOP3: PAND
0x00000000000100000000000000000000 .PAND

LDS: U
0x00000000000010000000000000000000 .U

LDG, STG, ATOMG, STS, ATOMS, LDS: r24
0x000000000000000000000000ff000000 DEFAULT

LDG, STG: r24type
0x00000000000000000000000000000000 .U32
0x00000000040000000000000000000000 .64
0x00000000040000000000000000000000 DEFAULT

ATOMG: r24type
0x00000000000000000000000000000000 .U32
0x00000000000000400000000000000000 .64
0x00000000000000400000000000000000 DEFAULT

STG, ATOMG, USHF, UIADD3: ur64
0x00000000080000000000000000000000 ALL

LDG: p64qnot
0x00000000000000080000000000000000 !

LDG, STG, ATOMG: E
0x00000000000001000000000000000000 .E

LDG, STG, ATOMG: cache
0x00000000000000000000000000000000 .EF
0x00000000001000000000000000000000 DEFAULT
0x00000000002000000000000000000000 .EL
0x00000000003000000000000000000000 .LU
0x00000000004000000000000000000000 .EU
0x00000000005000000000000000000000 .NA

LDG: ltc
0x00000000000000100000000000000000 .LTC64B
0x00000000000000200000000000000000 .LTC128B

LDG, LDC, ULDC, STG, LDS, STS: type
0x00000000000000000000000000000000 .U8
0x00000000000002000000000000000000 .S8
0x00000000000004000000000000000000 .U16
0x00000000000006000000000000000000 .S16
0x00000000000008000000000000000000 DEFAULT
0x0000000000000a000000000000000000 .64
0x0000000000000c000000000000000000 .128
0x0000000000000e000000000000000000 .U.128

LDC: isl
0x00000000000040000000000000000000 .IL
0x00000000000080000000000000000000 .IS
0x000000000000c0000000000000000000 .ISL

LDG, STG, ATOMG: const
0x00000000000000000000000000000000 .CONSTANT
0x00000000000080000000000000000000 DEFAULT
0x00000000000100000000000000000000 .STRONG
0x00000000000180000000000000000000 .MMIO

LDG, STG, ATOMG: scope
0x00000000000000000000000000000000 .CTA
0x00000000000020000000000000000000 .SM
0x00000000000040000000000000000000 .GPU
0x00000000000060000000000000000000 .SYS

LDG, STG, ATOMG: PRIVATE
0x00000000000010000000000000000000 .PRIVATE

LDG, LDS: ZD
0x00000000008000000000000000000000 .ZD

ATOMG, ATOMS: type
0x00000000000000000000000000000000 DEFAULT
0x00000000000002000000000000000000 .S32
0x00000000000004000000000000000000 .64
0x00000000000006000000000000000000 .F32.FTZ.RN
0x00000000000008000000000000000000 .F16x2.RN
0x0000000000000a000000000000000000 .S64
0x0000000000000c000000000000000000 .F64.RN

ATOMG, ATOMS: op
0x00000000000000000000000000000000 .ADD
0x00000000008000000000000000000000 .MIN
0x00000000010000000000000000000000 .MAX
0x00000000018000000000000000000000 .INC
0x00000000020000000000000000000000 .DEC
0x00000000028000000000000000000000 .AND
0x00000000030000000000000000000000 .OR
0x00000000038000000000000000000000 .XOR
0x00000000040000000000000000000000 .EXCH
0x00000000048000000000000000000000 .SAFEADD

BSSY, BRA, BSYNC, EXIT, YIELD, CALL, RET, WARPSYNC: p87
0x00000000038000000000000000000000 DEFAULT

BMOV: CLEAR
0x00000000001000000000000000000000 .CLEAR

BMOV: b24w5
0x00000000000000000000000000000000 B0
0x00000000000000000000000001000000 B1
0x00000000000000000000000002000000 B2
0x00000000000000000000000003000000 B3
0x00000000000000000000000004000000 B4
0x00000000000000000000000005000000 B5
0x00000000000000000000000006000000 B6
0x00000000000000000000000007000000 B7
0x00000000000000000000000008000000 B8
0x00000000000000000000000009000000 B9
0x0000000000000000000000000a000000 B10
0x0000000000000000000000000b000000 B11
0x0000000000000000000000000c000000 B12
0x0000000000000000000000000d000000 B13
0x0000000000000000000000000e000000 B14
0x0000000000000000000000000f000000 B15
0x00000000000000000000000010000000 THREAD_STATE_ENUM.0
0x00000000000000000000000011000000 THREAD_STATE_ENUM.1
0x00000000000000000000000012000000 THREAD_STATE_ENUM.2
0x00000000000000000000000013000000 THREAD_STATE_ENUM.3
0x00000000000000000000000014000000 THREAD_STATE_ENUM.4
0x00000000000000000000000015000000 TRAP_RETURN_PC.LO
0x00000000000000000000000016000000 TRAP_RETURN_PC.HI
0x00000000000000000000000017000000 TRAP_RETURN_MASK
0x00000000000000000000000018000000 MEXITED
0x00000000000000000000000019000000 MKILL
0x0000000000000000000000001a000000 MACTIVE
0x0000000000000000000000001b000000 MATEXIT
0x0000000000000000000000001c000000 OPT_STACK
0x0000000000000000000000001d000000 API_CALL_DEPTH
0x0000000000000000000000001e000000 ATEXIT_PC.LO
0x0000000000000000000000001f000000 ATEXIT_PC.HI

CS2R: type
0x00000000000000000000000000000000 .32
0x00000000000100000000000000000000 DEFAULT

S2R, S2UR, CS2R: sr
0x00000000000000000000000000000000 SR_LANEID
0x00000000000001000000000000000000 SR_CLOCK
0x00000000000002000000000000000000 SR_VIRTCFG
0x00000000000003000000000000000000 SR_VIRTID
0x00000000000004000000000000000000 SR4
0x00000000000005000000000000000000 SR5
0x00000000000006000000000000000000 SR6
0x00000000000007000000000000000000 SR7
0x00000000000008000000000000000000 SR8
0x00000000000009000000000000000000 SR9
0x0000000000000a000000000000000000 SR10
0x0000000000000b000000000000000000 SR11
0x0000000000000c000000000000000000 SR12
0x0000000000000d000000000000000000 SR13
0x0000000000000e000000000000000000 SR14
0x0000000000000f000000000000000000 SR_ORDERING_TICKET
0x00000000000010000000000000000000 SR_PRIM_TYPE
0x00000000000011000000000000000000 SR_INVOCATION_ID
0x00000000000012000000000000000000 SR_Y_DIRECTION
0x00000000000013000000000000000000 SR_THREAD_KILL
0x00000000000014000000000000000000 SM_SHADER_TYPE
0x00000000000015000000000000000000 SR_DIRECTCBEWRITEADDRESSLOW
0x00000000000016000000000000000000 SR_DIRECTCBEWRITEADDRESSHIGH
0x00000000000017000000000000000000 SR_DIRECTCBEWRITEENABLED
0x00000000000018000000000000000000 SR_MACHINE_ID_0
0x00000000000019000000000000000000 SR_MACHINE_ID_1
0x0000000000001a000000000000000000 SR_MACHINE_ID_2
0x0000000000001b000000000000000000 SR_MACHINE_ID_3
0x0000000000001c000000000000000000 SR_AFFINITY
0x0000000000001d000000000000000000 SR_INVOCATION_INFO
0x0000000000001e000000000000000000 SR_WSCALEFACTOR_XY
0x0000000000001f000000000000000000 SR_WSCALEFACTOR_Z
0x00000000000020000000000000000000 SR_TID
0x00000000000021000000000000000000 SR_TID.X
0x00000000000022000000000000000000 SR_TID.Y
0x00000000000023000000000000000000 SR_TID.Z
0x00000000000024000000000000000000 SR36
0x00000000000025000000000000000000 SR_CTAID.X
0x00000000000026000000000000000000 SR_CTAID.Y
0x00000000000027000000000000000000 SR_CTAID.Z
0x00000000000028000000000000000000 SR_NTID
0x00000000000029000000000000000000 SR_CirQueueIncrMinusOne
0x0000000000002a000000000000000000 SR_NLATC
0x0000000000002b000000000000000000 SR43
0x0000000000002c000000000000000000 SR_SM_SPA_VERSION
0x0000000000002d000000000000000000 SR_MULTIPASSSHADERINFO
0x0000000000002e000000000000000000 SR_LWINHI
0x0000000000002f000000000000000000 SR_SWINHI
0x00000000000030000000000000000000 SR_SWINLO
0x00000000000031000000000000000000 SR_SWINSZ
0x00000000000032000000000000000000 SR_SMEMSZ
0x00000000000033000000000000000000 SR_SMEMBANKS
0x00000000000034000000000000000000 SR_LWINLO
0x00000000000035000000000000000000 SR_LWINSZ
0x00000000000036000000000000000000 SR_LMEMLOSZ
0x00000000000037000000000000000000 SR_LMEMHIOFF
0x00000000000038000000000000000000 SR_EQMASK
0x00000000000039000000000000000000 SR_LTMASK
0x0000000000003a000000000000000000 SR_LEMASK
0x0000000000003b000000000000000000 SR_GTMASK
0x0000000000003c000000000000000000 SR_GEMASK
0x0000000000003d000000000000000000 SR_REGALLOC
0x0000000000003e000000000000000000 SR_BARRIERALLOC
0x0000000000003f000000000000000000 SR63
0x00000000000040000000000000000000 SR_GLOBALERRORSTATUS
0x00000000000041000000000000000000 SR65
0x00000000000042000000000000000000 SR_WARPERRORSTATUS
0x00000000000043000000000000000000 SR_VIRTUALSMID
0x00000000000044000000000000000000 SR_VIRTUALENGINEID
0x00000000000045000000000000000000 SR69
0x00000000000046000000000000000000 SR70
0x00000000000047000000000000000000 SR71
0x00000000000048000000000000000000 SR72
0x00000000000049000000000000000000 SR73
0x0000000000004a000000000000000000 SR74
0x0000000000004b000000000000000000 SR75
0x0000000000004c000000000000000000 SR76
0x0000000000004d000000000000000000 SR77
0x0000000000004e000000000000000000 SR78
0x0000000000004f000000000000000000 SR79
0x00000000000050000000000000000000 SR_CLOCKLO
0x00000000000051000000000000000000 SR_CLOCKHI
0x00000000000052000000000000000000 SR_GLOBALTIMERLO
0x00000000000053000000000000000000 SR_GLOBALTIMERHI
0x00000000000054000000000000000000 SR_ESR_PC
0x00000000000055000000000000000000 SR_ESR_PC_HI
0x00000000000056000000000000000000 SR86
0x00000000000057000000000000000000 SR87
0x00000000000058000000000000000000 SR88
0x00000000000059000000000000000000 SR89
0x0000000000005a000000000000000000 SR90
0x0000000000005b000000000000000000 SR91
0x0000000000005c000000000000000000 SR92
0x0000000000005d000000000000000000 SR93
0x0000000000005e000000000000000000 SR94
0x0000000000005f000000000000000000 SR95
0x00000000000060000000000000000000 SR_HWTASKID
0x00000000000061000000000000000000 SR_CIRCULARQUEUEENTRYINDEX
0x00000000000062000000000000000000 SR_CIRCULARQUEUEENTRYADDRESSLOW
0x00000000000063000000000000000000 SR_CIRCULARQUEUEENTRYADDRESSHIGH
0x00000000000064000000000000000000 SR_PM0
0x00000000000065000000000000000000 SR_PM_HI0
0x00000000000066000000000000000000 SR_PM1
0x00000000000067000000000000000000 SR_PM_HI1
0x00000000000068000000000000000000 SR_PM2
0x00000000000069000000000000000000 SR_PM_HI2
0x0000000000006a000000000000000000 SR_PM3
0x0000000000006b000000000000000000 SR_PM_HI3
0x0000000000006c000000000000000000 SR_PM4
0x0000000000006d000000000000000000 SR_PM_HI4
0x0000000000006e000000000000000000 SR_PM5
0x0000000000006f000000000000000000 SR_PM_HI5
0x00000000000070000000000000000000 SR_PM6
0x00000000000071000000000000000000 SR_PM_HI6
0x00000000000072000000000000000000 SR_PM7
0x00000000000073000000000000000000 SR_PM_HI7
0x00000000000074000000000000000000 SR_SNAP_PM0
0x00000000000075000000000000000000 SR_SNAP_PM_HI0
0x00000000000076000000000000000000 SR_SNAP_PM1
0x00000000000077000000000000000000 SR_SNAP_PM_HI1
0x00000000000078000000000000000000 SR_SNAP_PM2
0x00000000000079000000000000000000 SR_SNAP_PM_HI2
0x0000000000007a000000000000000000 SR_SNAP_PM3
0x0000000000007b000000000000000000 SR_SNAP_PM_HI3
0x0000000000007c000000000000000000 SR_SNAP_PM4
0x0000000000007d000000000000000000 SR_SNAP_PM_HI4
0x0000000000007e000000000000000000 SR_SNAP_PM5
0x0000000000007f000000000000000000 SR_SNAP_PM_HI5
0x00000000000080000000000000000000 SR_SNAP_PM6
0x00000000000081000000000000000000 SR_SNAP_PM_HI6
0x00000000000082000000000000000000 SR_SNAP_PM7
0x00000000000083000000000000000000 SR_SNAP_PM_HI7
0x00000000000084000000000000000000 SR_VARIABLE_RATE
0x00000000000085000000000000000000 SR_TTU_TICKET_INFO
0x00000000000086000000000000000000 SR134
0x00000000000087000000000000000000 SR135
0x00000000000088000000000000000000 SR136
0x00000000000089000000000000000000 SR137
0x0000000000008a000000000000000000 SR138
0x0000000000008b000000000000000000 SR139
0x0000000000008c000000000000000000 SR140
0x0000000000008d000000000000000000 SR141
0x0000000000008e000000000000000000 SR142
0x0000000000008f000000000000000000 SR143
0x00000000000090000000000000000000 SR144
0x00000000000091000000000000000000 SR145
0x00000000000092000000000000000000 SR146
0x00000000000093000000000000000000 SR147
0x00000000000094000000000000000000 SR148
0x00000000000095000000000000000000 SR149
0x00000000000096000000000000000000 SR150
0x00000000000097000000000000000000 SR151
0x00000000000098000000000000000000 SR152
0x00000000000099000000000000000000 SR153
0x0000000000009a000000000000000000 SR154
0x0000000000009b000000000000000000 SR155
0x0000000000009c000000000000000000 SR156
0x0000000000009d000000000000000000 SR157
0x0000000000009e000000000000000000 SR158
0x0000000000009f000000000000000000 SR159
0x000000000000a0000000000000000000 SR160
0x000000000000a1000000000000000000 SR161
0x000000000000a2000000000000000000 SR162
0x000000000000a3000000000000000000 SR163
0x000000000000a4000000000000000000 SR164
0x000000000000a5000000000000000000 SR165
0x000000000000a6000000000000000000 SR166
0x000000000000a7000000000000000000 SR167
0x000000000000a8000000000000000000 SR168
0x000000000000a9000000000000000000 SR169
0x000000000000aa000000000000000000 SR170
0x000000000000ab000000000000000000 SR171
0x000000000000ac000000000000000000 SR172
0x000000000000ad000000000000000000 SR173
0x000000000000ae000000000000000000 SR174
0x000000000000af000000000000000000 SR175
0x000000000000b0000000000000000000 SR176
0x000000000000b1000000000000000000 SR177
0x000000000000b2000000000000000000 SR178
0x000000000000b3000000000000000000 SR179
0x000000000000b4000000000000000000 SR180
0x000000000000b5000000000000000000 SR181
0x000000000000b6000000000000000000 SR182
0x000000000000b7000000000000000000 SR183
0x000000000000b8000000000000000000 SR184
0x000000000000b9000000000000000000 SR185
0x000000000000ba000000000000000000 SR186
0x000000000000bb000000000000000000 SR187
0x000000000000bc000000000000000000 SR188
0x000000000000bd000000000000000000 SR189
0x000000000000be000000000000000000 SR190
0x000000000000bf000000000000000000 SR191
0x000000000000c0000000000000000000 SR192
0x000000000000c1000000000000000000 SR193
0x000000000000c2000000000000000000 SR194
0x000000000000c3000000000000000000 SR195
0x000000000000c4000000000000000000 SR196
0x000000000000c5000000000000000000 SR197
0x000000000000c6000000000000000000 SR198
0x000000000000c7000000000000000000 SR199
0x000000000000c8000000000000000000 SR200
0x000000000000c9000000000000000000 SR201
0x000000000000ca000000000000000000 SR202
0x000000000000cb000000000000000000 SR203
0x000000000000cc000000000000000000 SR204
0x000000000000cd000000000000000000 SR205
0x000000000000ce000000000000000000 SR206
0x000000000000cf000000000000000000 SR207
0x000000000000d0000000000000000000 SR208
0x000000000000d1000000000000000000 SR209
0x000000000000d2000000000000000000 SR210
0x000000000000d3000000000000000000 SR211
0x000000000000d4000000000000000000 SR212
0x000000000000d5000000000000000000 SR213
0x000000000000d6000000000000000000 SR214
0x000000000000d7000000000000000000 SR215
0x000000000000d8000000000000000000 SR216
0x000000000000d9000000000000000000 SR217
0x000000000000da000000000000000000 SR218
0x000000000000db000000000000000000 SR219
0x000000000000dc000000000000000000 SR220
0x000000000000dd000000000000000000 SR221
0x000000000000de000000000000000000 SR222
0x000000000000df000000000000000000 SR223
0x000000000000e0000000000000000000 SR224
0x000000000000e1000000000000000000 SR225
0x000000000000e2000000000000000000 SR226
0x000000000000e3000000000000000000 SR227
0x000000000000e4000000000000000000 SR228
0x000000000000e5000000000000000000 SR229
0x000000000000e6000000000000000000 SR230
0x000000000000e7000000000000000000 SR231
0x000000000000e8000000000000000000 SR232
0x000000000000e9000000000000000000 SR233
0x000000000000ea000000000000000000 SR234
0x000000000000eb000000000000000000 SR235
0x000000000000ec000000000000000000 SR236
0x000000000000ed000000000000000000 SR237
0x000000000000ee000000000000000000 SR238
0x000000000000ef000000000000000000 SR239
0x000000000000f0000000000000000000 SR240
0x000000000000f1000000000000000000 SR241
0x000000000000f2000000000000000000 SR242
0x000000000000f3000000000000000000 SR243
0x000000000000f4000000000000000000 SR244
0x000000000000f5000000000000000000 SR245
0x000000000000f6000000000000000000 SR246
0x000000000000f7000000000000000000 SR247
0x000000000000f8000000000000000000 SR248
0x000000000000f9000000000000000000 SR249
0x000000000000fa000000000000000000 SR250
0x000000000000fb000000000000000000 SR251
0x000000000000fc000000000000000000 SR252
0x000000000000fd000000000000000000 SR253
0x000000000000fe000000000000000000 SR254
0x000000000000ff000000000000000000 SRZ
'''


def format_flags(flag_str, gram):
    flag_str = strip_space(flag_str)

    # Create flag dict
    flag_dict = {}
    for key in gram.keys():
        flag_dict[key] = {}

    ops = []
    names = []
    for line in flag_str.split('\n'):
        m = re.search(rf'^({hexx}) (.+)', line)
        if m:
            value = int(m.group(1), base=0)
            for op in ops:
                for name in names:
                    flag_dict[op][name][m.group(2)] = value
        else:
            ops, names = line.split(': ')
            ops = ops.split(', ')
            names = names.split(', ')
            # Create new dict for this flag.
            for op in ops:
                for name in names:
                    flag_dict[op][name] = {}
    return flag_dict


flags_61: dict = format_flags(flags_str_61, grammar_61)
flags_75: dict = format_flags(flags_str_75, grammar_75)


def encode_ctrl(asm):
    _, wait_bm, rb_idx, wb_idx, yield_, stall = asm.split(":")
    wait_bm = 0 if wait_bm == '--' else int(wait_bm, base=16)
    rb_idx = 7 if rb_idx == '-' else int(rb_idx) - 1
    wb_idx = 7 if wb_idx == '-' else int(wb_idx) - 1
    yield_ = 0 if yield_ == 'y' or yield_ == 'Y' else 1
    stall = int(stall, base=16)
    return wait_bm << 11 | rb_idx << 8 | wb_idx << 5 | yield_ << 4 | stall


def encode_ctrls(ctrl1, ctrl2, ctrl3):
    return ctrl1 | ctrl2 << 21 | ctrl3 << 42


def encode_reuse(captured_dict):
    reuse_code = 0x0
    if captured_dict.get('reuse1') == '.reuse':
        reuse_code |= 0x1
    if captured_dict.get('reuse2') == '.reuse':
        reuse_code |= 0x2
    if captured_dict.get('reuse3') == '.reuse':
        reuse_code |= 0x4
    return reuse_code << 17


def encode_instruction(op, gram, captured_dict, instr, arch):
    code = gram['code']
    if arch < 70:
        flag = flags_61[op] if op in flags_61 else {}
    else:
        flag = flags_75[op] if op in flags_75 else {}

    # Process predicate.
    # 0xf0000是P寄存器，高位位1,是!PX，低3位表示P0-P6, 7表示不使用P寄存器
    if 'noPred' not in captured_dict:
        p = int(instr['pred_reg']) if instr['pred_reg'] and instr['pred_reg'] != 'T' else 0x7
        if instr['pred_not']:
            p |= 0x8
        if arch < 70:
            code ^= p << 16
        else:
            code ^= p << 12

    # Process flags and operands
    for k, v in captured_dict.items():

        if k in flag:
            if v:
                if v in flag[k]:
                    flag_value = flag[k][v]
                elif 'ALL' in flag[k]:
                    flag_value = flag[k]['ALL']
                else:
                    flag_value = 0
                code ^= flag_value
            elif 'DEFAULT' in flag[k]:
                flag_value = flag[k]['DEFAULT']
                code ^= flag_value
        if k in operands and v:
            code ^= operands[k](v)

    # Process reuse
    reuse = encode_reuse(captured_dict)

    # Process ctrl
    ctrl = encode_ctrl(instr['ctrl'])
    ctrl |= reuse

    return ctrl, code


def decode_ctrl(sub_code):
    stall = sub_code & 0xf
    yield_ = (sub_code >> 4) & 0x1
    wb_idx = (sub_code >> 5) & 0x7
    rb_idx = (sub_code >> 8) & 0x7
    wait_bm = (sub_code >> 11) & 0x3f
    reuse = (sub_code >> 17) & 0xf
    return {
        'schedule': 1,
        'reuse': reuse,
        'wait_bm': wait_bm,
        'rb_idx': rb_idx,
        'wb_idx': wb_idx,
        'yield': yield_,
        'stall': stall,
    }


def decode_ctrls(code):
    ctrl1 = code & 0x1fffff
    ctrl2 = (code >> 21) & 0x1fffff
    ctrl3 = (code >> 42) & 0x1fffff
    return decode_ctrl(ctrl1), decode_ctrl(ctrl2), decode_ctrl(ctrl3)


def print_ctrl(ctrl):
    """
    打印控制码
    wait_bm：Wait Dependency Barriers Masks，6位bit map，表示该指令等待哪些Dependency Barrier
    rb_idx:  Read Dependency Barrier，数字1-6，用于设置非固定周期指令的读后写依赖
    wb_idx:  Write Dependency Barrier，数字1-6，用于设置非固定周期指令的写后读依赖
    yield:   控制warp调度，标识当前warp可以被换出
    stall:   指令延迟周期数
    :param ctrl: 包含控制码的dict，由decode_ctrl产生
    :return: 便于阅读的控制码字符串
    """
    schedule = '-' if ctrl['schedule'] else 'K'
    wait_bm = f"{ctrl['wait_bm']:02x}" if ctrl['wait_bm'] else '--'
    rb_idx = '-' if ctrl['rb_idx'] == 7 else ctrl['rb_idx'] + 1
    wb_idx = '-' if ctrl['wb_idx'] == 7 else ctrl['wb_idx'] + 1
    yield_ = '-' if ctrl['yield'] else 'Y'

    return f"{schedule}:{wait_bm}:{rb_idx}:{wb_idx}:{yield_}:{ctrl['stall']:x}"


def print_reuse(reuse):
    reuse1 = '1' if reuse & 1 else '-'
    reuse2 = '2' if reuse & 2 else '-'
    reuse3 = '3' if reuse & 4 else '-'
    reuse4 = '4' if reuse & 8 else '-'
    return f'{reuse1}{reuse2}{reuse3}{reuse4}'


def print_instr(instr):
    return f"{instr['pred']:>5s} {instr['op']}{instr['rest']}"


def get_jump_offset(rest):
    m = re.search(fr'{i20w24}\s*;', rest)
    if m:
        return int(m.group('i20w24'), base=0)
    else:
        raise Exception(f'Cannot recognize jump offset {rest}')


def addr2line_num(address, arch):
    if arch < 70:
        line_num = address // 32 * 3 + (address % 32 // 8)
        if address % 32 != 0:
            line_num -= 1
    else:
        line_num = address // 16
    return line_num


def line_num2addr(line_num, arch):
    if arch < 70:
        address = (line_num // 3 * 4 + line_num % 3 + 1) * 0x8
    else:
        address = line_num * 16
    return address


def process_asm_line(line, line_num):
    m = re.search(fr'^\s*{CTRL_RE}\s+{INST_RE}', line)
    if m:
        # line_num ctrl pred pred_not pred_reg op rest
        instr = {'line_num': line_num, **m.groupdict()}
        if instr['pred'] is None:
            instr['pred'] = ''
        return instr
    else:
        return None


def process_sass_ctrl_line(line):
    m = re.search(rf'^\s+{CODE_RE}', line)
    if m:
        binary = int(m.group('code'), base=0)
        return decode_ctrls(binary)
    else:
        return []


def process_sass_line(line):
    m = re.search(rf'^\s+{SASS_RE}', line)
    if m:
        instr = m.groupdict()
        if instr['pred'] is None:
            instr['pred'] = ''
        return instr
    else:
        return {}


def process_sass_code(line, instr):
    m = re.search(rf'^\s+{CODE_RE}', line)
    if m:
        code_hi = m.group('code')
        instr['code'] = f'{code_hi}{instr["code"][2:]}'
        return instr
    else:
        return {}
