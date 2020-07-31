#!/usr/bin/env python3
# coding: utf-8

import pycuda.driver as drv
import pycuda.tools
import pycuda.autoinit
import numpy as np

THREADS = 128

mod = drv.module_from_file('test.cubin')
kernel = mod.get_function("kTest")

result = np.array([0]*THREADS).astype(np.int32)
result_gpu, result_size = mod.get_global('result')

duration = np.array([0]*THREADS).astype(np.int32)
duration_gpu, duration_size = mod.get_global('duration')

drv.memcpy_htod(result_gpu, result)
drv.memcpy_htod(duration_gpu, duration)

kernel(block=(THREADS, 1, 1))

drv.memcpy_dtoh(result, result_gpu)
drv.memcpy_dtoh(duration, duration_gpu)
print(f'Result = {np.unique(result)}')
print(f'Duration = {np.mean(duration)} (min={np.min(duration)} max={np.max(duration)})')


# from graphviz import Digraph
#
# g = Digraph()
#
# g.edge('S2R R5, SR_TID.X;', 'IMAD.WIDE.U32 R2, R5, 0x4, R2;', label='R5')
# g.edge('MOV R2, UR5;', 'IMAD.WIDE.U32 R2, R5, 0x4, R2;', label='R2')
# g.edge('UMOV UR5, 32@lo(result);', 'MOV R2, UR5;', label='UR5')
# g.edge('IMAD.WIDE.U32 R2, R5, 0x4, R2;', 'STG.E.SYS [R2], R7;', label='R2')
# g.edge('MOV R3, UR6;', 'STG.E.SYS [R2], R7;', label='R3')
# g.edge('UMOV UR6, 32@hi(result);', 'MOV R3, UR6;', label='UR6')
# g.edge('IMAD.MOV.U32 R7, RZ, RZ, 0x3;', 'STG.E.SYS [R2], R7;', label='R7')
#
# g.edge('UMOV UR5, 32@lo(duration);', '29 MOV R2, UR5;', label='UR5')
# g.edge('UMOV UR6, 32@hi(duration);', '30 MOV R3, UR6;', label='UR6')
# g.edge('S2R R5, SR_TID.X;', '31 IMAD.WIDE.U32 R2, R5, 0x4, R2;', label='R5')
# g.edge('29 MOV R2, UR5;', '31 IMAD.WIDE.U32 R2, R5, 0x4, R2;', label='R2')
# g.edge('CS2R.32 R0, SR_CLOCKLO;', 'IADD3 R5, R0, -UR4, RZ;', label='R0')
# g.edge('S2UR UR4, SR_CLOCKLO;', 'IADD3 R5, R0, -UR4, RZ;', label='UR4')
# g.edge('31 IMAD.WIDE.U32 R2, R5, 0x4, R2;', 'STG.E.SYS [R2], R5;', label='R2')
# g.edge('30 MOV R3, UR6;', 'STG.E.SYS [R2], R5;', label='R3')
# g.edge('IADD3 R5, R0, -UR4, RZ;', 'STG.E.SYS [R2], R5;', label='R5')
