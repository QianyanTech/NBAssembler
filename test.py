#!/usr/bin/env python3
# coding: utf-8

import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "0"

import pycuda.driver as cuda
import pycuda.tools
import pycuda.autoinit
import numpy as np

THREADS = 1

mod = cuda.module_from_file('test.cubin')
kernel = mod.get_function("kTest")

a = np.array([0b1111]*THREADS).astype(np.uint32)
a_gpu, duration_size = mod.get_global('a')

c = np.array([0]*THREADS).astype(np.uint32)
c_gpu, result_size = mod.get_global('c')

cuda.memcpy_htod(a_gpu, a)

kernel(block=(1, 1, 1))

cuda.memcpy_dtoh(c, c_gpu)

print(f'Result = {np.unique(c)[0]:#0x}')
