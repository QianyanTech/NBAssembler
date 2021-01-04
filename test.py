#!/usr/bin/env python3
# coding: utf-8

import os
os.environ["CUDA_DEVICE_ORDER"] = "PCI_BUS_ID"
os.environ["CUDA_VISIBLE_DEVICES"] = "1"

import pycuda.driver as cuda
import pycuda.tools
import pycuda.autoinit
import numpy as np

THREADS = 1

mod = cuda.module_from_file('test.cubin')
kernel = mod.get_function("kTest")

a = np.array([0x70000]*THREADS).astype(np.uint32)
a_gpu, a_size = mod.get_global('a')

b = np.array([0xf]*THREADS).astype(np.uint32)
b_gpu, b_size = mod.get_global('b')

d = np.array([0]*THREADS).astype(np.uint32)
d_gpu, d_size = mod.get_global('d')

cuda.memcpy_htod(a_gpu, a)
cuda.memcpy_htod(b_gpu, b)

kernel(block=(1, 1, 1))

cuda.memcpy_dtoh(d, d_gpu)

print(f'Result = {np.unique(d)[0]:#0x}')
