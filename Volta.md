| Opcode                              | Description                                                  |
| ----------------------------------- | ------------------------------------------------------------ |
| **Floating Point Instructions**     |                                                              |
| FADD                                | FP32 Add                                                     |
| FADD32I                             | FP32 Add                                                     |
| FCHK                                | Floating-point Range Check                                   |
| FFMA32I                             | FP32 Fused Multiply and Add                                  |
| FFMA                                | FP32 Fused Multiply and Add                                  |
| FMNMX                               | FP32 Minimum/Maximum                                         |
| FMUL                                | FP32 Multiply                                                |
| FMUL32I                             | FP32 Multiply                                                |
| FSEL                                | Floating Point Select                                        |
| FSET                                | FP32 Compare And Set                                         |
| FSETP                               | FP32 Compare And Set Predicate                               |
| FSWZADD                             | FP32 Swizzle Add                                             |
| MUFU                                | FP32 Multi Function Operation                                |
| HADD2                               | FP16 Add                                                     |
| HADD2_32I                           | FP16 Add                                                     |
| HFMA2                               | FP16 Fused Mutiply Add                                       |
| HFMA2_32I                           | FP16 Fused Mutiply Add                                       |
| HMMA                                | Matrix Multiply and Accumulate                               |
| HMUL2                               | FP16 Multiply                                                |
| HMUL2_32I                           | FP16 Multiply                                                |
| HSET2                               | FP16 Compare And Set                                         |
| HSETP2                              | FP16 Compare And Set Predicate                               |
| DADD                                | FP64 Add                                                     |
| DFMA                                | FP64 Fused Mutiply Add                                       |
| DMUL                                | FP64 Multiply                                                |
| DSETP                               | FP64 Compare And Set Predicate                               |
| **Integer Instructions**            |                                                              |
| BMSK                                | Bitfield Mask                                                |
| BREV                                | Bit Reverse                                                  |
| FLO                                 | Find Leading One                                             |
| IABS                                | Integer Absolute Value                                       |
| IADD                                | Integer Addition                                             |
| IADD3                               | 3-input Integer Addition                                     |
| IADD32I                             | Integer Addition                                             |
| IDP                                 | Integer Dot Product and Accumulate                           |
| IDP4A                               | Integer Dot Product and Accumulate                           |
| IMAD                                | Integer Multiply And Add                                     |
| IMMA                                | Integer Matrix Multiply and Accumulate                       |
| IMNMX                               | Integer Minimum/Maximum                                      |
| IMUL                                | Integer Multiply                                             |
| IMUL32I                             | Integer Multiply                                             |
| ISCADD                              | Scaled Integer Addition                                      |
| ISCADD32I                           | Scaled Integer Addition                                      |
| ISETP                               | Integer Compare And Set Predicate                            |
| LEA                                 | LOAD Effective Address                                       |
| LOP                                 | Logic Operation                                              |
| LOP3                                | Logic Operation                                              |
| LOP32I                              | Logic Operation                                              |
| POPC                                | Population count                                             |
| SHF                                 | Funnel Shift                                                 |
| SHL                                 | Shift Left                                                   |
| SHR                                 | Shift Right                                                  |
| VABSDIFF                            | Absolute Difference                                          |
| VABSDIFF4                           | Absolute Difference                                          |
| **Conversion Instructions**         |                                                              |
| F2F                                 | Floating Point To Floating Point Conversion                  |
| F2I                                 | Floating Point To Integer Conversion                         |
| I2F                                 | Integer To Floating Point Conversion                         |
| I2I                                 | Integer To Integer Conversion                                |
| I2IP                                | Integer To Integer Conversion and Packing                    |
| FRND                                | Round To Integer                                             |
| **Movement Instructions**           |                                                              |
| MOV                                 | Move                                                         |
| MOV32I                              | Move                                                         |
| PRMT                                | Permute Register Pair                                        |
| SEL                                 | Select Source with Predicate                                 |
| SGXT                                | Sign Extend                                                  |
| SHFL                                | Warp Wide Register Shuffle                                   |
| **Predicate Instructions**          |                                                              |
| PLOP3                               | Predicate Logic Operation                                    |
| PSETP                               | Combine Predicates and Set Predicate                         |
| P2R                                 | Move Predicate Register To Register                          |
| R2P                                 | Move Register To Predicate Register                          |
| **Load/Store Instructions**         |                                                              |
| LD                                  | Load from generic Memory                                     |
| LDC                                 | Load Constant                                                |
| LDG                                 | Load from Global Memory                                      |
| LDL                                 | Load within Local Memory Window                              |
| LDS                                 | Load within Shared Memory Window                             |
| ST                                  | Store to Generic Memory                                      |
| STG                                 | Store to Global Memory                                       |
| STL                                 | Store within Local or Shared Window                          |
| STS                                 | Store within Local or Shared Window                          |
| MATCH                               | Match Register Values Across Thread Group                    |
| QSPC                                | Query Space                                                  |
| ATOM                                | Atomic Operation on Generic Memory                           |
| ATOMS                               | Atomic Operation on Shared Memory                            |
| ATOMG                               | Atomic Operation on Global Memory                            |
| RED                                 | Reduction Operation on Generic Memory                        |
| CCTL                                | Cache Control                                                |
| CCTLL                               | Cache Control                                                |
| ERRBAR                              | Error Barrier                                                |
| MEMBAR                              | Memory Barrier                                               |
| CCTLT                               | Texture Cache Control                                        |
| **Texture Instructions**            |                                                              |
| TEX                                 | Texture Fetch                                                |
| TLD                                 | Texture Load                                                 |
| TLD4                                | Texture Load 4                                               |
| TMML                                | Texture MipMap Level                                         |
| TXD                                 | Texture Fetch With Derivatives                               |
| TXQ                                 | Texture Query                                                |
| **Surface Instructions**            |                                                              |
| SUATOM                              | Atomic Op on Surface Memory                                  |
| SULD                                | Surface Load                                                 |
| SURED                               | Reduction Op on Surface Memory                               |
| SUST                                | Surface Store                                                |
| **Control Instructions**            |                                                              |
| BMOV                                | Move Convergence Barrier State                               |
| BPT                                 | BreakPoint/Trap                                              |
| BRA                                 | Relative Branch                                              |
| BREAK                               | Break out of the Specified Convergence Barrier               |
| BRX                                 | Relative Branch Indirect                                     |
| BSSY                                | Barrier Set Convergence Synchronization Point                |
| BSYNC                               | Synchronize Threads on a Convergence Barrier                 |
| CALL                                | Call Function                                                |
| EXIT                                | Exit Program                                                 |
| JMP                                 | Absolute Jump                                                |
| JMX                                 | Absolute Jump Indirect                                       |
| KILL                                | Kill Thread                                                  |
| NANOSLEEP                           | Suspend Execution                                            |
| RET                                 | Return From Subroutine                                       |
| RPCMOV                              | PC Register Move                                             |
| RTT                                 | Return From Trap                                             |
| WARPSYNC                            | Synchronize Threads in Warp                                  |
| YIELD                               | Yield Control                                                |
| **Miscellaneous Instructions**      |                                                              |
| B2R                                 | Move Barrier To Register                                     |
| BAR                                 | Barrier Synchronization                                      |
| CS2R                                | Move Special Register to Register                            |
| DEPBAR                              | Dependency Barrier                                           |
| GETLMEMBASE                         | Get Local Memory Base Address                                |
| LEPC                                | Load Effective PC                                            |
| NOP                                 | No Operation                                                 |
| PMTRIG                              | Performance Monitor Trigger                                  |
| R2B                                 | Move Register to Barrier                                     |
| S2R                                 | Move Special Register to Register                            |
| SETCTAID                            | Set CTA ID                                                   |
| SETLMEMBASE                         | Set Local Memory Base Address                                |
| VOTE                                | Vote Across SIMD Thread Group                                |