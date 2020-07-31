# CUDA 汇编指令

## XMAD

16位整数乘加

```lisp
XMAD d, a, b, c;
; d = a.lo * b.lo + c
; .PSL  d = (a.lo * b.lo ) << 16 + c
; .MRG  d = ((a.lo * b.lo + c) & 0xffff) | (b.lo << 16)
; .CBCC d = a.lo * b.lo + c + (b.lo << 16)
; .CHI  d = a.lo * b.lo + c.hi
; .CLO  d = a.lo * b.lo + c.lo
```

例子：

```lisp
; 32位(A)乘16位(B)
; d = a * b.lo + c
XMAD d, a, b, c;
XMAD.PSL d, a.h1, b, d;
```

```lisp
; 32位(a)乘32位(b)
; d = a * b + c
XMAD d, a, b, c;
XMAD.MRG x, a, b.h1, RZ;
XMAD.PSL.CBCC d, a.h1, x.h1, d;
; .PSL.CBCC d = (a.lo * b.lo) << 16 + c + (b.lo << 16)
```

```lisp
; mad.hi.u32
; d = a * b + c
XMAD x, a, b, RZ;
XMAD x2, a, b.H1, RZ;
XMAD x3, a.H1, b.H1, c;
XMAD.CHI x1, a.H1, b, x;
IADD3.RS d, x1, x2, x3;
```

## LOP3.LUT

各种逻辑运算组合。查表法

```lisp
; a = 0xf0; b = 0xcc; c = 0xaa;
LOP3.LUT d, a, b, c, 0xXX;
; 0x3c d = a ^ b
; 0x40 d = a & b & ~c
; 0x48 d = b & (a ^ c)
; 0x80 d = a & b & c
; 0x96 d = a ^ b ^ c
; 0xab d = (a & b | c) ^ a
; 0xc0 d = a & b
; 0xe2 d = a & b | ~b & c
; 0xf4 d = a | (b & ~c)
; 0xf8 d = a | (b & c)
; 0xfc d = a | b
; 0xfe d = a | b | c
```

## BFI

插入一段bit位

```lisp
BFI d, a, b, c
; a是bit field
; c是被插入的寄存器
; b.lo 低8位 插入位置
; b.hi 高8位 插入长度
; for (i=0; i<len && pos+i<=msb; i++) {
;    f[pos+i] = a[i];
; }
```

## BFE

提取一段bit位

```lisp
BFE.U32 d, a, b
; a是被提取的寄存器
; b.lo 低8位 提取位置
; b.hi 高8位 提取长度
; d = (a>>b)&((1<<c)-1)
```

## VOTE.ALL

每个参与运算的thread的a值都为True，则d为True

更详细的猜测：d有32位，每个线程使用一位，True则相应位置1。

```lisp
VOTE.ALL d, a, b
;a 存储要参与判断的值
;b 32位，membermask，每一位对应一个thread，为1则该thread参与vote运算。
```

## FLO

第一个1的位置

```lisp
FLO.U32 d, a
; 例如a=1, 第一个1在第0位上，所以d=0
```

## POPC

统计1的个数

```lisp
POPC d, a
; 例如a=0x00000003,即低2位是1，所以d=2
```

## S2R

读取特殊寄存器，存入寄存器。

```lisp
S2R d, SR_LTMASK
; SR_LTMASK LANEID=0时，SR_LTMASK=0。只确认过这一种。
; SR_LTMASK 猜测：使用bit来表示LANEID。
; SR_LTMASK 例如LANEID=0,则LTMASK=0;LANEID=5,则LTMASK=0xf;LANEID=7,则LTMASK=0x3f;
; SR_CTAID blockIdx
; SR_TID threadIdx
; SR_LANEID laneid
```

其他特殊寄存器可以参考PTX文档。

## SHFL.IDX

warp内寄存器广播

```lisp
SHFL.IDX PT, d, val, src_lane, warp_size
; 从laneID=src_lane的线程中，取寄存器val，存入寄存器d
```

## SHFL.BFLY

warp内寄存器操作

```lisp
SHFL.BFLY PT, d, val, lane_mask, warp_size
; 从laneID=src_lane ^ lane_mask的线程中，取寄存器val，存入寄存器d
```

## ISCADD

整数位移加法

```lisp
ISCADD d, a, b, c
; d = b + (a<<c) 
```

## LEA

64位地址运算

```lisp
LEA d.lo.cc, a.lo, b.lo, c
LEA.HI.X d.hi, a.lo, b.hi, a.hi, c
; d = b + (a<<c) 

LEA.HI d, a.lo, b, a.hi, c
; d = b + (a<<c>>32)
```

## SHF

循环移位

```lisp
SHF.[R|L].U64.[Hi] d, a.lo, b, a.Hi
SHF.R.U64 d, a.lo, b, a.Hi
; 将a循环右移b位，d取结果的低32位
SHF.R.U64.Hi 
; 结果的高32位
```

## ICMP

整数与0比较并选择赋值

```lisp
ICMP.[OP] d, a, b, c
; d = c op 0 ? a : b
ICMP.EQ d, a, b, c
; d = c == 0 ? a : b
```

## SEL

判断逻辑值并选择赋值

```lisp
SEL d, a, b, c
; d = c ? a : b
```

## ATOM RED

原子操作，ATOM返回旧值，RED不返回旧值。

## LOP.PASS_B

按位取反

```lisp
LOP.PASS_B R6, RZ, ~R2;
; not.b32 %r6, %r2;
```

## R2P PR

根据寄存器的值批量设置P寄存器

```lisp
R2P PR, a, b;
; c = a&b;
; if (c>>n)&1: %pn = True
```

## IMNMX

min max函数

```gas
IMNMX.U32 d, a, b, PT;
; d = min(a, b)
IMNMX.U32 d, a, b, !PT;
; d = max(a, b)
```

