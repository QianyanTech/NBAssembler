| Opcode                              | Description                                                  |
| ----------------------------------- | ------------------------------------------------------------ |
| **Floating Point Instructions**     |                                                              |
| FADD                                | FP32 Add                                                     |
| FCHK                                | Single Precision FP Divide Range Check                       |
| FCMP                                | FP32 Compare to Zero and Select Source                       |
| FFMA                                | FP32 Fused Multiply and Add                                  |
| FMNMX                               | FP32 Minimum/Maximum                                         |
| FMUL                                | FP32 Multiply                                                |
| FSET                                | FP32 Compare And Set                                         |
| FSETP                               | FP32 Compare And Set Predicate                               |
| FSWZADD                             | FP32 Add used for FSWZ emulation                             |
| MUFU                                | Multi Function Operation                                     |
| RRO                                 | Range Reduction Operator FP                                  |
| DADD                                | FP64 Add                                                     |
| DFMA                                | FP64 Fused Mutiply Add                                       |
| DMNMX                               | FP64 Minimum/Maximum                                         |
| DMUL                                | FP64 Multiply                                                |
| DSET                                | FP64 Compare And Set                                         |
| DSETP                               | FP64 Compare And Set Predicate                               |
| HADD2                               | FP16 Add                                                     |
| HFMA2                               | FP16 Fused Mutiply Add                                       |
| HMUL2                               | FP16 Multiply                                                |
| HSET2                               | FP16 Compare And Set                                         |
| HSETP2                              | FP16 Compare And Set Predicate                               |
| **Integer Instructions**            |                                                              |
| BFE                                 | Bit Field Extract                                            |
| BFI                                 | Bit Field Insert                                             |
| FLO                                 | Find Leading One                                             |
| IADD                                | Integer Addition                                             |
| IADD3                               | 3-input Integer Addition                                     |
| ICMP                                | Integer Compare to Zero and Select Source                    |
| IMAD                                | Integer Multiply And Add                                     |
| IMADSP                              | Extracted Integer Multiply And Add.                          |
| IMNMX                               | Integer Minimum/Maximum                                      |
| IMUL                                | Integer Multiply                                             |
| ISCADD                              | Scaled Integer Addition                                      |
| ISET                                | Integer Compare And Set                                      |
| ISETP                               | Integer Compare And Set Predicate                            |
| LEA                                 | Compute Effective Address                                    |
| LOP                                 | Logic Operation                                              |
| LOP3                                | 3-input Logic Operation                                      |
| POPC                                | Population count                                             |
| SHF                                 | Funnel Shift                                                 |
| SHL                                 | Shift Left                                                   |
| SHR                                 | Shift Right                                                  |
| XMAD                                | Integer Short Multiply Add                                   |
| **Conversion Instructions**         |                                                              |
| F2F                                 | Floating Point To Floating Point Conversion                  |
| F2I                                 | Floating Point To Integer Conversion                         |
| I2F                                 | Integer To Floating Point Conversion                         |
| I2I                                 | Integer To Integer Conversion                                |
| **Movement Instructions**           |                                                              |
| MOV                                 | Move                                                         |
| PRMT                                | Permute Register Pair                                        |
| SEL                                 | Select Source with Predicate                                 |
| SHFL                                | Warp Wide Register Shuffle                                   |
| **Predicate/CC Instructions**       |                                                              |
| CSET                                | Test Condition Code And Set                                  |
| CSETP                               | Test Condition Code and Set Predicate                        |
| PSET                                | Combine Predicates and Set                                   |
| PSETP                               | Combine Predicates and Set Predicate                         |
| P2R                                 | Move Predicate Register To Register                          |
| R2P                                 | Move Register To Predicate/CC Register                       |
| **Texture Instructions**            |                                                              |
| TEX                                 | Texture Fetch                                                |
| TLD                                 | Texture Load                                                 |
| TLD4                                | Texture Load 4                                               |
| TXQ                                 | Texture Query                                                |
| TEXS                                | Texture Fetch with scalar/non-vec4 source/destinations       |
| TLD4S                               | Texture Load 4 with scalar/non-vec4 source/destinations      |
| TLDS                                | Texture Load with scalar/non-vec4 source/destinations        |
| **Compute Load/Store Instructions** |                                                              |
| LD                                  | Load from generic Memory                                     |
| LDC                                 | Load Constant                                                |
| LDG                                 | Load from Global Memory                                      |
| LDL                                 | Load within Local Memory Window                              |
| LDS                                 | Local within Shared Memory Window                            |
| ST                                  | Store to generic Memory                                      |
| STG                                 | Store to global Memory                                       |
| STL                                 | Store within Local or Shared Window                          |
| STS                                 | Store within Local or Shared Window                          |
| ATOM                                | Atomic Operation on generic Memory                           |
| ATOMS                               | Atomic Operation on Shared Memory                            |
| RED                                 | Reduction Operation on generic Memory                        |
| CCTL                                | Cache Control                                                |
| CCTLL                               | Cache Control                                                |
| MEMBAR                              | Memory Barrier                                               |
| CCTLT                               | Texture Cache Control                                        |
| **Surface Memory Instructions**     |                                                              |
| SUATOM                              | Atomic Op on Surface Memory                                  |
| SULD                                | Surface Load                                                 |
| SURED                               | Reduction Op on Surface Memory                               |
| SUST                                | Surface Store                                                |
| **Control Instructions**            |                                                              |
| BRA                                 | Relative Branch                                              |
| BRX                                 | Relative Branch Indirect                                     |
| JMP                                 | Absolute Jump                                                |
| JMX                                 | Absolute Jump Indirect                                       |
| SSY                                 | Set Synchronization Point                                    |
| SYNC                                | Converge threads after conditional branch                    |
| CAL                                 | Relative Call                                                |
| JCAL                                | Absolute Call                                                |
| PRET                                | Pre-Return From Subroutine                                   |
| RET                                 | Return From Subroutine                                       |
| BRK                                 | Break                                                        |
| PBK                                 | Pre-Break                                                    |
| CONT                                | Continue                                                     |
| PCNT                                | Pre-continue                                                 |
| EXIT                                | Exit Program                                                 |
| PEXIT                               | Pre-Exit                                                     |
| BPT                                 | BreakPoint/Trap                                              |
| **Miscellaneous Instructions**      |                                                              |
| NOP                                 | No Operation                                                 |
| CS2R                                | Move Special Register to Register                            |
| S2R                                 | Move Special Register to Register                            |
| B2R                                 | Move Barrier To Register                                     |
| BAR                                 | Barrier Synchronization                                      |
| R2B                                 | Move Register to Barrier                                     |
| VOTE                                | Vote Across SIMD Thread Group                                |