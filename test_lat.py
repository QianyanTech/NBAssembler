#!/usr/bin/env python3
# coding: utf-8

import pycuda.driver as drv
import pycuda.tools
import pycuda.autoinit
import numpy as np

THREADS = 256

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
print(f'Duration = {np.mean(duration)}')
