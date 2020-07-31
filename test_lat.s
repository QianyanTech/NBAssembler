.compute_75

.sm_75

.global: result
    .align 4
    .zero {1024*1024}

.global: duration
    .align 4
    .zero {1024*1024}

.kernel: kTest
    .reg begin, UR0
    .reg gp, UR1
    .reg gp_hi, UR2
    .reg end, R0
    .reg duration, R0
    .reg tid, R1
    .reg gp, R2
    .reg gp_hi, R3
    .reg result, R4
    -:--:-:1:-:1    S2R R_tid, SR_TID.X;
    -:--:-:-:-:2    UMOV UR_gp, 32@lo(result);
    -:--:-:-:-:1    UMOV UR_gp_hi, 32@hi(result);
    -:--:-:-:-:5    MOV R_result, 0x100;
    // -:--:-:-:-:5    MOV R5, 0x100;
    // -:--:-:-:-:5    MOV R6, 0x100;
    // -:--:-:-:-:5    MOV R7, 0x100;
    // -:--:-:-:-:5    MOV R8, 0x100;
    // -:--:-:-:-:5    MOV R9, 0x100;
    // -:--:-:-:-:5    MOV R10, 0x100;
    // -:--:-:-:-:5    MOV R11, 0x100;
    -:--:-:-:-:2    MOV R_gp, UR_gp;
    -:--:-:-:Y:5    MOV R_gp_hi, UR_gp_hi;
    -:01:-:-:Y:a    IMAD.WIDE.U32 R_gp, R_tid, 0x4, R_gp;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    // -:--:-:-:-:a    NOP;
    -:--:-:-:-:1    S2UR UR_begin, SR_CLOCKLO;

    // -:--:-:-:-:1    CS2R.32 R_end, SR_CLOCKLO;
    
    // -:--:-:-:-:a    FLO.U32 R7, R6;
    // -:--:-:-:-:5    NOP;
    // -:--:-:-:-:4    FSEL R7, RZ, 0x4, !PT;
    // -:--:-:-:-:4    IMNMX.U32 R7, RZ, 0x4, !PT;
    // -:--:-:-:-:4    MOV R7, 0x4;
    // -:--:-:-:-:4    IADD3 R7, RZ, 0x4, RZ;
    // -:--:-:-:-:5    IMAD.MOV.U32 R7, RZ, RZ, 0x4;

    -:--:-:-:-:1    FLO.U32 R_result, R_tid;
    -:--:-:-:-:1    FLO.U32 R5, RZ;
    -:--:-:-:-:1    FLO.U32 R6, RZ;
    // -:--:-:-:-:1    FLO.U32 R7, RZ;
    // -:--:-:-:-:1    FLO.U32 R8, RZ;
    // -:--:-:-:-:1    FLO.U32 R9, RZ;
    // -:--:-:-:-:1    FLO.U32 R10, RZ;
    -:--:-:-:-:a    FLO.U32 R11, RZ;
    -:--:-:-:-:5    NOP;

    // -:--:-:-:-:1    FLO.U32 R_result, R7;
    // -:--:-:-:-:1    IMNMX.U32 R_result, R7, 0xff, PT;
    // -:--:-:-:-:1    MOV R_result, R7;
    // -:--:-:-:-:1    IADD3 R_result, R7, RZ, RZ;
    // -:--:-:-:-:1    IMAD.MOV.U32 R_result, RZ, RZ, R7;
    
    // -:--:-:-:-:a    FLO.U32 R7, R6;
    // -:--:-:-:-:5    NOP;
    // -:--:-:-:-:5    IMNMX.U32 R7, RZ, 0x3, !PT;
    // -:--:-:-:-:5    MOV R7, 0x3;
    // -:--:-:-:-:5    IADD3 R7, RZ, 0x3, RZ;
    // -:--:-:-:-:5    IMAD.MOV.U32 R7, RZ, RZ, 0x3;

    -:--:-:-:-:1    CS2R.32 R_end, SR_CLOCKLO;
    -:--:-:-:-:1    STG.E.SYS [R_gp], R_result;
    -:--:-:-:-:5    BAR.SYNC 0x0;
    -:--:-:-:-:2    UMOV UR_gp, 32@lo(duration);
    -:--:-:-:-:1    UMOV UR_gp_hi, 32@hi(duration);
    -:--:-:-:-:2    MOV R_gp, UR_gp;
    -:--:-:-:Y:5    MOV R_gp_hi, UR_gp_hi;
    -:--:-:-:-:1    IMAD.WIDE.U32 R_gp, R_tid, 0x4, R_gp;
    -:--:-:-:Y:9    IADD3 R_duration, R_end, -UR_begin, RZ;
    -:--:-:-:-:1    STG.E.SYS [R_gp], R_duration;
    -:--:-:-:-:5    EXIT;
L_0:
    -:--:-:-:Y:0    BRA `(L_0);
    -:--:-:-:Y:0    NOP;
    -:--:-:-:Y:0    NOP;