# NB Assembler

Assembler and Decompiler for NVIDIA (Maxwell Pascal Volta Turing Ampere) GPUs.


## Requirements:

* Python >= 3.8
* CUDA >= 6.5 (Only requires `nvdisasm` for disassembly or testing) 


## Supported NVIDIA GPUs:

Maxwell (SM50, SM52, SM53)

Pascal (SM60, SM61, SM62)

Volta (SM70, SM72)

Turing (SM75)

Ampere (SM80, SM86)


## Install

```
python setup.py install
```


## Use

```bash
# help
nbasm -h

# usage: nbasm [-h] [-V] {list,das,as,pre,pdas,test,det} ...

# Assembler and Decompiler for NVIDIA (Maxwell Pascal Volta Turing Ampere) GPUs.

# optional arguments:
#   -h, --help            show this help message and exit
#   -V, --version         Print version information on this tool.

# subcommands:
#   {list,das,as,pre,pdas,test,det}
#     list                list cubin info
#     das                 disassemble cubin
#     as                  assemble asm
#     pre                 preprocess asm
#     pdas                disassemble asm to ptx
#     test                test assembler by disassemble and then assemble
#     det                 detect machine code bits

# examples
nbasm list ethash.cubin 
nbasm das -k Search -o ethash_search.s ethash.cubin
nbasm as -D DEBUG=True -o ethash.cubin ethash_search.s
nbasm pdas -o ethash.ptx ethash.s
```

## ASM Grammar

```assembly
# 单行注释
# 反汇编出来的其它用不到的元信息将写入文件头的注释。汇编时忽略。
/* 多行注释 */
.compute_75  # virtual_arch
.sm_75  # arch
.global: NAME  # 全局变量
	.align 8
	.zero 368
	.byte 0xff, 0xff, 0xff, 0x7f
	.short 0x0412
	.word 0x00000020
	.quad 0x366803807ff7021f
.constants: NAME  # 用户自定义常量
    .align 4
    .zero 4
.constants2: NAME  # 编译器生成的常量，一般由于代码中有指令编码存不下的立即数
    .align 4
    .zero 4

# 引用其它文件

# include汇编文件，直接在这个位置替换位汇编文件的内容
.include "source.s"

# include Python源代码，将会先执行这个Python脚本，执行后，使用Python上向文中out_变量的内容在这个位置替换
.include "source.py"

.constants: {python expression}  # {}中间的内容（单行）为Python表达式，计算表达式结果并在这个位置替换
    ...

# {}中间内容（多行）则视为Python代码，执行Python代码后使用Python上向文中out_变量的内容在这个位置替换
{
# 例如，条件include
if define1:
    out += '.include "source1.s"\n'
else:
    out += '.include "source2.s"\n'
out = '''
...
'''
}

.kernel: NAME  # kernel定义与代码
	# 普通寄存器别名映射，支持单个映射和批量映射（类似数组的用法）
	.reg NAME, Rxx
	# Uniform寄存器别名映射
	.reg NAME, URxx-xx
	# Pred寄存器别名映射
	.reg NAME, Pxx
	# Uniform Pred寄存器别名映射
	.reg NAME, UPxx
	# Kernel参数
	.param ordinal, NAME, SIZE_IN_BYTES
	# shared
	.shared SIZE_IN_BYTES

.L_label: #标签
    # 指令：/*地址*/  控制码   pred 指令.标志...  操作数, ...;    /* 指令编码 */ # reuse编码
	/*1dd0*/  -:--:-:-:Y:8  @!P6 IMAD.SHL.U32 R2, R2, 0x2, RZ;    /* 0x000fd000078e00ff000000020202e824 */ # ----
	# 控制码： schedule_flag:Wait_barrier_mask:read_barrier_index:write_barrier_index:yield:stall
	#	schedule_flag: 调度标志，仅供nbasm的调度器使用。默认自动调度。设置为'K'表示已经手工调好了这条指令的控制码，调度器忽略这条指令。
	#	Wait_barrier_mask: 等待read_barrier、write_barrier的位图
	#	read_barrier_index: 不定周期指令设置读后写依赖
	#	write_barrier_index: 不定周期指令设置写后读依赖
	#	yield: 让出,表示当前warp可以被换出。一般用于stall超过4个周期情况
	#	stall: 本条指令调度后，下一条指令延迟开始的周期数
```

## Related projects

[AsFermi](https://github.com/hyqneuron/asfermi), an SASS assembler for NVIDIA Fermi GPUs. By Hou Yunqing.

[KeplerAs](https://github.com/xiuxiazhang/KeplerAs), an SASS assembler for NVIDIA Kepler. By Xiuxia Zhang.

[MaxAs](https://github.com/NervanaSystems/maxas), an SASS assembler for NVIDIA Maxwell and Pascal. By Scott Gray.

[TuringAs](https://github.com/daadaada/turingas), an SASS assembler for NVIDIA Volta and Turing. By Da Yan.



This project is released under the MIT License.

-- Alvin Zhu