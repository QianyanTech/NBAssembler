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

a = np.array([0x1000000000]*THREADS).astype(np.uint64)
a_gpu, a_size = mod.get_global('a')

b = np.array([0x100000010]*THREADS).astype(np.uint64)
b_gpu, b_size = mod.get_global('b')

c = np.array([0]*THREADS).astype(np.uint64)
c_gpu, c_size = mod.get_global('c')

cuda.memcpy_htod(a_gpu, a)
cuda.memcpy_htod(b_gpu, b)

kernel(block=(1, 1, 1))

cuda.memcpy_dtoh(c, c_gpu)

print(f'Result = {np.unique(c)[0]:#0x}')
