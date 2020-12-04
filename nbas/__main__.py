# coding: utf-8


import argparse

from .cubin import Cubin, strip_space, strip_comment
from .kernel import Kernel
from .tool import detect


def list_cubin(cubin_path, kernel_name, global_only):
    cubin = Cubin()
    cubin.load(cubin_path, global_only)
    print(cubin.header.print())

    if kernel_name:
        if kernel_name in cubin.kernel_dict:
            kernels = [cubin.kernel_dict[kernel_name], ]
        else:
            print(f'{kernel_name.decode()} nor Found.')
            return 0
    else:
        kernels = cubin.kernel_dict.values()
        print('Global:')
        for global_ in cubin.global_dict.values():
            print(f'    {global_.name.decode()}, Align:{global_.align}, Size:{global_.size}')
        print('Constant:')
        for constant in cubin.constant_dict.values():
            print(f'    {constant.name.decode()}, Align:{constant.align}, Size:{constant.size}')
    for kernel in kernels:
        # if Symbol.STB_STR[kernel.linkage] != 'GLOBAL':
        #     continue
        if kernel.constant2:
            print('Constant:')
            name = kernel.constant2.name.decode()
            size = kernel.constant2.size
            align = kernel.constant2.align
            print(f'    {name}, Align:{align}, Size:{size}')
        print(kernel.print_meta())


def disassemble(cubin_path, kernel_names, asm_path, strip, global_only):
    cubin = Cubin()
    cubin.load(cubin_path, global_only)
    # 输出各种元信息
    header_asm = cubin.header.print() + '\n'
    global_asm = ''
    constant_asm = ''
    kernel_asm = ''

    if kernel_names:
        kernels = []
        for kernel_name in kernel_names:
            kernel_name = kernel_name.encode()
            if kernel_name in cubin.kernel_dict:
                kernels.append(cubin.kernel_dict[kernel_name])
            else:
                print(f'{kernel_name.decode()} nor Found.')
                return 0
    else:
        kernels = cubin.kernel_dict.values()

    consts = set()
    globals_ = set()
    for kernel in kernels:
        # if Symbol.STB_STR[kernel.linkage] != 'GLOBAL':
        #     continue
        kernel.disassemble()
        # kernel.schedule()
        # kernel.sort_banks()
        cubin.map_constant3(kernel)
        kernel.map_jump()
        kernel.map_global()
        kernel.map_constant0()
        kernel.mark_const2()
        kernel_asm += '\n' + kernel.print()
        consts = consts.union(kernel.consts)
        globals_ = globals_.union(kernel.globals)

    for global_ in cubin.global_dict.values():
        if global_.name in globals_:
            global_asm += global_.print() + '\n'
    for global_ in cubin.global_init_dict.values():
        if global_.name in globals_:
            global_asm += global_.print() + '\n'
    for constant in cubin.constant_dict.values():
        if constant.name in consts or 'ALL_CONST3' in consts:
            constant_asm += constant.print() + '\n'

    asm = header_asm + global_asm + constant_asm + kernel_asm

    if strip:
        asm = strip_comment(asm)

    if asm_path:
        with open(asm_path, 'w') as f:
            f.write(asm)
    else:
        print(asm, end='')


def disassemble_ptx(asm_path, ptx_path, define_list):
    cubin = Cubin()

    define_dict = {}
    for define in define_list:
        if not define:
            continue
        d = define.split('=')
        if len(d) < 2:
            exec(f'{define} = True', define_dict)
        else:
            exec(f'{define}', define_dict)

    cubin.load_asm(asm_path, define_dict)

    header_ptx = cubin.header.print_ptx() + '\n'

    global_ptx = ''
    constant_ptx = ''
    for global_ in cubin.global_dict.values():
        global_ptx += global_.print_ptx() + '\n'

    for global_ in cubin.global_init_dict.values():
        global_ptx += global_.print_ptx() + '\n'

    for constant in cubin.constant_dict.values():
        constant_ptx += constant.print_ptx() + '\n'

    kernel_ptx = ''
    for kernel in cubin.kernel_dict.values():
        kernel.mark_const2(replace=True)
        kernel.disassemble_ptx()
        kernel_ptx += '\n' + kernel.print_ptx()

    ptx = header_ptx + global_ptx + constant_ptx + kernel_ptx

    if ptx_path:
        with open(ptx_path, 'w') as f:
            f.write(ptx)
    else:
        print(ptx, end='')


def assemble(asm_path, out_cubin_path, define_list, out_asm_path, sort_banks):
    if not out_cubin_path:
        out_cubin_path = 'out.cubin'
    cubin = Cubin()

    define_dict = {}
    for define in define_list:
        if not define:
            continue
        d = define.split('=')
        if len(d) < 2:
            exec(f'{define} = True', define_dict)
        else:
            exec(f'{define}', define_dict)

    cubin.load_asm(asm_path, define_dict)

    for kernel in cubin.kernel_dict.values():
        # Unmap global, const0, const3
        cubin.unmap_constant3(kernel)
        kernel.unmap_reg()
        kernel.unmap_global()
        kernel.unmap_constant0()
        kernel.unmap_jump()
        # kernel.schedule()
        if sort_banks:
            kernel.sort_banks()
        kernel.assemble()

    # 生成elf数据
    cubin.gen_sections()
    cubin.gen_symbols()
    cubin.gen_rels()
    cubin.gen_nv_info()
    cubin.gen_program()

    cubin.write(out_cubin_path)

    if out_asm_path:
        header_asm = cubin.header.print() + '\n'
        global_asm = ''
        constant_asm = ''
        kernel_asm = ''
        for kernel in cubin.kernel_dict.values():
            cubin.map_constant3(kernel)
            kernel.map_global()
            kernel.map_constant0()
            kernel.map_jump(rel=True)
            kernel.mark_const2()
            kernel_asm += '\n' + kernel.print()
        for global_ in cubin.global_dict.values():
            global_asm += global_.print() + '\n'
        for global_ in cubin.global_init_dict.values():
            global_asm += global_.print() + '\n'
        for constant in cubin.constant_dict.values():
            constant_asm += constant.print() + '\n'
        asm = header_asm + global_asm + constant_asm + kernel_asm
        with open(out_asm_path, 'w') as f:
            f.write(asm)


def preprocess(asm_path, out_asm_path, define_list, strip):
    cubin = Cubin()

    define_dict = {}
    for define in define_list:
        if not define:
            continue
        d = define.split('=')
        if len(d) < 2:
            exec(f'{define} = True', define_dict)
        else:
            exec(f'{define}', define_dict)

    cubin.load_asm(asm_path, define_dict)
    header_asm = cubin.header.print() + '\n'
    global_asm = ''
    constant_asm = ''
    kernel_asm = ''

    consts = set()
    globals_ = set()
    for kernel in cubin.kernel_dict.values():
        # Unmap global, const0, const3
        cubin.unmap_constant3(kernel)
        kernel.unmap_reg()
        kernel.unmap_global()
        kernel.unmap_constant0()
        kernel.unmap_jump()
        kernel.schedule()
        kernel.sort_banks()
        cubin.map_constant3(kernel)
        kernel.map_global()
        kernel.map_constant0()
        kernel.map_jump(rel=True)
        kernel.mark_const2()
        kernel_asm += '\n' + kernel.print()
        consts = consts.union(kernel.consts)
        globals_ = globals_.union(kernel.globals)

    for global_ in cubin.global_dict.values():
        if global_.name in globals_:
            global_asm += global_.print() + '\n'
    for global_ in cubin.global_init_dict.values():
        if global_.name in globals_:
            global_asm += global_.print() + '\n'
    for constant in cubin.constant_dict.values():
        if constant.name in consts or 'ALL_CONST3' in consts:
            constant_asm += constant.print() + '\n'

    asm = header_asm + global_asm + constant_asm + kernel_asm

    if strip:
        asm = strip_comment(asm)

    if out_asm_path:
        with open(out_asm_path, 'w') as f:
            f.write(asm)
    else:
        print(asm, end='')


def test_cubin(cubin_path, kernel_names, global_only, check=False):
    cubin = Cubin()
    cubin_new = Cubin()

    cubin.load(cubin_path, global_only)

    # header
    header_asm = cubin.header.print()
    header_asm = strip_space(header_asm)
    cubin_new.load_asm_header(header_asm)

    # data
    data_asm = ''
    for global_ in cubin.global_dict.values():
        data_asm += global_.print() + '\n'

    for global_ in cubin.global_init_dict.values():
        data_asm += global_.print() + '\n'

    for constant in cubin.constant_dict.values():
        data_asm += constant.print() + '\n'
    data_asm = strip_space(data_asm)
    cubin_new.load_asm_data(data_asm)

    # check const3, global
    # for data_dict, data_dict_new in zip([cubin.global_dict, cubin.global_init_dict, cubin.constant_dict],
    #                                     [cubin_new.global_dict, cubin_new.global_init_dict, cubin_new.constant_dict]):
    #     if data_dict != data_dict_new:
    #         print('Global data failed:')

    if kernel_names:
        kernels = []
        for kernel_name in kernel_names:
            kernel_name = kernel_name.encode()
            if kernel_name in cubin.kernel_dict:
                kernels.append(cubin.kernel_dict[kernel_name])
            else:
                print(f'{kernel_name.decode()} nor Found.')
                return 0
    else:
        kernels = cubin.kernel_dict.values()

    for kernel in kernels:
        print(f'Kernel:{kernel.name.decode()}... ', end='')
        kernel.disassemble()

        # disable if align mismatch
        # cubin.map_constant3(kernel)
        # kernel.map_global()
        # kernel.map_constant0()

        kernel.map_jump()

        # kernel
        kernel_new = Kernel(name=kernel.name, arch=cubin_new.arch)
        cubin_new.kernel_dict[kernel.name] = kernel_new
        if kernel.constant2:
            data_asm = kernel.constant2.print()
            data_asm = strip_space(data_asm)
            cubin_new.load_asm_data(data_asm)

            # check const2
            # if kernel_new.constant2 != kernel.constant2:
            #     print('constant2 failed:')

        asm = kernel.print_meta() + kernel.print_asm()
        asm = strip_space(asm)
        kernel_new.load_asm(asm)

        kernel_new.unmap_jump()

        # disable if align mismatch
        # kernel_new.unmap_constant0()
        # kernel_new.unmap_global()
        # cubin_new.unmap_constant3(kernel_new)
        if check:
            kernel.check_reg_bank()
        binary = kernel_new.assemble(kernel.binary)

        if binary:
            print(f'Test Pass.')
        else:
            print(f'Test failed.')

    # 生成elf数据
    cubin_new.gen_sections()
    cubin_new.gen_symbols()
    cubin_new.gen_rels()
    cubin_new.gen_nv_info()
    cubin_new.gen_program()

    # if cubin.header != cubin_new.header:
    #     print('Header failed:')
    #     print(f'original: {cubin.header}')
    #     print(f'     new: {cubin_new.header}')
    #
    # if cubin.section_dict != cubin_new.section_dict:
    #     print('Sections failed:')
    #
    # if cubin.symbol_dict != cubin_new.symbol_dict:
    #     print('Symbols failed:')


def main():
    description = 'NB Assembler for NVIDIA (Maxwell Pascal Volta Turing Ampere) GPUs.'
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('-V', '--version', action='store_true', help='Print version information on this tool.')
    subparsers = parser.add_subparsers(dest='cmd', title='subcommands')

    parser_list = subparsers.add_parser('list', help='list cubin info')
    parser_list.add_argument('cubin', help='input cubin', metavar='CUBIN')
    parser_list.add_argument('-k', '--kernel', metavar='KERNEL', type=str, default='', help='kernel name')
    parser_list.add_argument('-g', '--global_only', action='store_true', help='ignore non global FUNC')

    parser_das = subparsers.add_parser('das', help='disassemble cubin')
    parser_das.add_argument('cubin', help='input cubin', metavar='CUBIN')
    parser_das.add_argument('-k', '--kernels', metavar='KERNELS', nargs='+', type=str, default='', help='kernel names')
    parser_das.add_argument('-o', '--output', metavar='OUTPUT', type=str, default='', help='output asm file path')
    parser_das.add_argument('-s', '--strip', action='store_true', help='strip comment')
    parser_das.add_argument('-g', '--global_only', action='store_true', help='ignore non global FUNC')

    parser_as = subparsers.add_parser('as', help='assemble asm')
    parser_as.add_argument('asm', help='input asm', metavar='ASM')
    # parser_as.add_argument('-m', '--merge', metavar='CUBIN', type=str,
    #                        help='merge into CUBIN, overwrite same symbols, write to OUTPUT')
    parser_as.add_argument('-o', '--output', metavar='OUTPUT', type=str, default='', help='output cubin path')
    parser_as.add_argument('-D', '--define', metavar='DEFINE', nargs='+', type=str, default='',
                           help='define variable for embedded python code')
    parser_as.add_argument('-d', '--debug', metavar='OUTPUT_ASM', type=str, default='', help='output asm for debug')
    parser_as.add_argument('-s', '--sort', action='store_true', help='sort banks')

    parser_pre = subparsers.add_parser('pre', help='preprocess asm')
    parser_pre.add_argument('asm', help='input asm', metavar='ASM')
    parser_pre.add_argument('-D', '--define', metavar='DEFINE', nargs='+', type=str, default='',
                            help='define variable for embedded python code')
    parser_pre.add_argument('-o', '--output', metavar='OUTPUT', type=str, default='', help='output asm file path')
    parser_pre.add_argument('-s', '--strip', action='store_true', help='strip comment')

    parser_pdas = subparsers.add_parser('pdas', help='disassemble asm to ptx')
    parser_pdas.add_argument('asm', help='input asm', metavar='ASM')
    parser_pdas.add_argument('-D', '--define', metavar='DEFINE', nargs='+', type=str, default='',
                             help='define variable for embedded python code')
    parser_pdas.add_argument('-o', '--output', metavar='OUTPUT', type=str, default='', help='output ptx file path')

    parser_test = subparsers.add_parser('test', help='test assembler by disassemble and then assemble')
    parser_test.add_argument('cubin', help='input cubin', metavar='CUBIN')
    parser_test.add_argument('-c', '--check', action='store_true', help='Detect register bank conflicts')
    parser_test.add_argument('-k', '--kernels', metavar='KERNELS', nargs='+', type=str, default='', help='kernel names')
    parser_test.add_argument('-g', '--global_only', action='store_true', help='ignore non global FUNC')

    parser_det = subparsers.add_parser('det', help='detect machine code bits')
    parser_det.add_argument('code', help='input code', metavar='CODE')
    parser_det.add_argument('-a', '--arch', help='code arch', metavar='ARCH', type=int, default=61)
    parser_det.add_argument('-r', '--range', nargs=2, metavar=('BEGIN', 'END'), type=int,
                            help='detect machine code by flip [BEGIN,END] bit')
    args = parser.parse_args()

    if args.version:
        print(description)
        print('version 11.1.1')
    elif args.cmd == 'list':
        list_cubin(cubin_path=args.cubin, kernel_name=args.kernel.encode(), global_only=args.global_only)
    elif args.cmd == 'das':
        disassemble(cubin_path=args.cubin, kernel_names=args.kernels, asm_path=args.output, strip=args.strip,
                    global_only=args.global_only)
    elif args.cmd == 'as':
        assemble(asm_path=args.asm, out_cubin_path=args.output, define_list=args.define, out_asm_path=args.debug,
                 sort_banks=args.sort)
    elif args.cmd == 'pre':
        preprocess(asm_path=args.asm, out_asm_path=args.output, define_list=args.define, strip=args.strip)
    elif args.cmd == 'pdas':
        disassemble_ptx(asm_path=args.asm, ptx_path=args.output, define_list=args.define)
    elif args.cmd == 'test':
        test_cubin(cubin_path=args.cubin, kernel_names=args.kernels, global_only=args.global_only, check=args.check)
    elif args.cmd == 'det':
        code = args.code
        begin, end = args.range
        arch = args.arch
        detect(int(code, base=0), begin, end, arch)


if __name__ == '__main__':
    main()
