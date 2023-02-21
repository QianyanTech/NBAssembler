.compute_75

.sm_75

.global: result
    .align 4
    .zero 1024

.global: duration
    .align 4
    .zero 1024

.kernel: kTest
    .max_registers 255
    --:-:1:-:1    S2R R5, SR_TID.X;
    --:-:-:-:2    UMOV UR5, 32@lo(result);
    --:-:-:-:1    UMOV UR6, 32@hi(result);
    --:-:-:-:5    MOV R7, 0x1;
    --:-:-:-:2    MOV R2, UR5;
    --:-:-:Y:5    MOV R3, UR6;
    01:-:-:Y:a    IMAD.WIDE.U32 R2, R5, 0x4, R2;
    --:-:-:-:1    S2UR UR4, SR_CLOCKLO;
    --:-:-:-:5    IMAD.MOV.U32 R7, RZ, RZ, 0x3;
    --:-:-:-:1    STG.E.SYS [R2], R7;
    --:-:-:-:1    CS2R.32 R0, SR_CLOCKLO;
    --:-:-:-:5    BAR.SYNC 0x0;
    --:-:-:-:2    UMOV UR5, 32@lo(duration);
    --:-:-:-:1    UMOV UR6, 32@hi(duration);
    --:-:-:-:2    MOV R2, UR5;
    --:-:-:Y:5    MOV R3, UR6;
    --:-:-:-:1    IMAD.WIDE.U32 R2, R5, 0x4, R2;
    --:-:-:Y:9    IADD3 R5, R0, -UR4, RZ;
    --:-:-:-:1    STG.E.SYS [R2], R5;
    --:-:-:-:5    EXIT;
L_0:
    --:-:-:Y:0    BRA `(L_0);
    --:-:-:Y:0    NOP;
    --:-:-:Y:0    NOP;