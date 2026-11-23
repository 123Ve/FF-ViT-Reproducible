// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2025.1 (64-bit)
// Tool Version Limit: 2025.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
/***************************** Include Files *********************************/
#include "xvit_block_top.h"

/************************** Function Implementation *************************/
#ifndef __linux__
int XVit_block_top_CfgInitialize(XVit_block_top *InstancePtr, XVit_block_top_Config *ConfigPtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(ConfigPtr != NULL);

    InstancePtr->Control_BaseAddress = ConfigPtr->Control_BaseAddress;
    InstancePtr->Control_r_BaseAddress = ConfigPtr->Control_r_BaseAddress;
    InstancePtr->IsReady = XIL_COMPONENT_IS_READY;

    return XST_SUCCESS;
}
#endif

void XVit_block_top_Start(XVit_block_top *InstancePtr) {
    u32 Data;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL) & 0x80;
    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL, Data | 0x01);
}

u32 XVit_block_top_IsDone(XVit_block_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL);
    return (Data >> 1) & 0x1;
}

u32 XVit_block_top_IsIdle(XVit_block_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL);
    return (Data >> 2) & 0x1;
}

u32 XVit_block_top_IsReady(XVit_block_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL);
    // check ap_start to see if the pcore is ready for next input
    return !(Data & 0x1);
}

void XVit_block_top_EnableAutoRestart(XVit_block_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL, 0x80);
}

void XVit_block_top_DisableAutoRestart(XVit_block_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_AP_CTRL, 0);
}

void XVit_block_top_Set_num_layers(XVit_block_top *InstancePtr, u32 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_NUM_LAYERS_DATA, Data);
}

u32 XVit_block_top_Get_num_layers(XVit_block_top *InstancePtr) {
    u32 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_NUM_LAYERS_DATA);
    return Data;
}

void XVit_block_top_Set_ext_weights(XVit_block_top *InstancePtr, u64 Data) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_r_BaseAddress, XVIT_BLOCK_TOP_CONTROL_R_ADDR_EXT_WEIGHTS_DATA, (u32)(Data));
    XVit_block_top_WriteReg(InstancePtr->Control_r_BaseAddress, XVIT_BLOCK_TOP_CONTROL_R_ADDR_EXT_WEIGHTS_DATA + 4, (u32)(Data >> 32));
}

u64 XVit_block_top_Get_ext_weights(XVit_block_top *InstancePtr) {
    u64 Data;

    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Data = XVit_block_top_ReadReg(InstancePtr->Control_r_BaseAddress, XVIT_BLOCK_TOP_CONTROL_R_ADDR_EXT_WEIGHTS_DATA);
    Data += (u64)XVit_block_top_ReadReg(InstancePtr->Control_r_BaseAddress, XVIT_BLOCK_TOP_CONTROL_R_ADDR_EXT_WEIGHTS_DATA + 4) << 32;
    return Data;
}

void XVit_block_top_InterruptGlobalEnable(XVit_block_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_GIE, 1);
}

void XVit_block_top_InterruptGlobalDisable(XVit_block_top *InstancePtr) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_GIE, 0);
}

void XVit_block_top_InterruptEnable(XVit_block_top *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_IER);
    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_IER, Register | Mask);
}

void XVit_block_top_InterruptDisable(XVit_block_top *InstancePtr, u32 Mask) {
    u32 Register;

    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    Register =  XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_IER);
    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_IER, Register & (~Mask));
}

void XVit_block_top_InterruptClear(XVit_block_top *InstancePtr, u32 Mask) {
    Xil_AssertVoid(InstancePtr != NULL);
    Xil_AssertVoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    XVit_block_top_WriteReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_ISR, Mask);
}

u32 XVit_block_top_InterruptGetEnabled(XVit_block_top *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_IER);
}

u32 XVit_block_top_InterruptGetStatus(XVit_block_top *InstancePtr) {
    Xil_AssertNonvoid(InstancePtr != NULL);
    Xil_AssertNonvoid(InstancePtr->IsReady == XIL_COMPONENT_IS_READY);

    return XVit_block_top_ReadReg(InstancePtr->Control_BaseAddress, XVIT_BLOCK_TOP_CONTROL_ADDR_ISR);
}

