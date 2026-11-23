// ==============================================================
// Vitis HLS - High-Level Synthesis from C, C++ and OpenCL v2025.1 (64-bit)
// Tool Version Limit: 2025.05
// Copyright 1986-2022 Xilinx, Inc. All Rights Reserved.
// Copyright 2022-2025 Advanced Micro Devices, Inc. All Rights Reserved.
// 
// ==============================================================
#ifndef XVIT_BLOCK_TOP_H
#define XVIT_BLOCK_TOP_H

#ifdef __cplusplus
extern "C" {
#endif

/***************************** Include Files *********************************/
#ifndef __linux__
#include "xil_types.h"
#include "xil_assert.h"
#include "xstatus.h"
#include "xil_io.h"
#else
#include <stdint.h>
#include <assert.h>
#include <dirent.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <sys/mman.h>
#include <unistd.h>
#include <stddef.h>
#endif
#include "xvit_block_top_hw.h"

/**************************** Type Definitions ******************************/
#ifdef __linux__
typedef uint8_t u8;
typedef uint16_t u16;
typedef uint32_t u32;
typedef uint64_t u64;
#else
typedef struct {
#ifdef SDT
    char *Name;
#else
    u16 DeviceId;
#endif
    u64 Control_BaseAddress;
    u64 Control_r_BaseAddress;
} XVit_block_top_Config;
#endif

typedef struct {
    u64 Control_BaseAddress;
    u64 Control_r_BaseAddress;
    u32 IsReady;
} XVit_block_top;

typedef u32 word_type;

/***************** Macros (Inline Functions) Definitions *********************/
#ifndef __linux__
#define XVit_block_top_WriteReg(BaseAddress, RegOffset, Data) \
    Xil_Out32((BaseAddress) + (RegOffset), (u32)(Data))
#define XVit_block_top_ReadReg(BaseAddress, RegOffset) \
    Xil_In32((BaseAddress) + (RegOffset))
#else
#define XVit_block_top_WriteReg(BaseAddress, RegOffset, Data) \
    *(volatile u32*)((BaseAddress) + (RegOffset)) = (u32)(Data)
#define XVit_block_top_ReadReg(BaseAddress, RegOffset) \
    *(volatile u32*)((BaseAddress) + (RegOffset))

#define Xil_AssertVoid(expr)    assert(expr)
#define Xil_AssertNonvoid(expr) assert(expr)

#define XST_SUCCESS             0
#define XST_DEVICE_NOT_FOUND    2
#define XST_OPEN_DEVICE_FAILED  3
#define XIL_COMPONENT_IS_READY  1
#endif

/************************** Function Prototypes *****************************/
#ifndef __linux__
#ifdef SDT
int XVit_block_top_Initialize(XVit_block_top *InstancePtr, UINTPTR BaseAddress);
XVit_block_top_Config* XVit_block_top_LookupConfig(UINTPTR BaseAddress);
#else
int XVit_block_top_Initialize(XVit_block_top *InstancePtr, u16 DeviceId);
XVit_block_top_Config* XVit_block_top_LookupConfig(u16 DeviceId);
#endif
int XVit_block_top_CfgInitialize(XVit_block_top *InstancePtr, XVit_block_top_Config *ConfigPtr);
#else
int XVit_block_top_Initialize(XVit_block_top *InstancePtr, const char* InstanceName);
int XVit_block_top_Release(XVit_block_top *InstancePtr);
#endif

void XVit_block_top_Start(XVit_block_top *InstancePtr);
u32 XVit_block_top_IsDone(XVit_block_top *InstancePtr);
u32 XVit_block_top_IsIdle(XVit_block_top *InstancePtr);
u32 XVit_block_top_IsReady(XVit_block_top *InstancePtr);
void XVit_block_top_EnableAutoRestart(XVit_block_top *InstancePtr);
void XVit_block_top_DisableAutoRestart(XVit_block_top *InstancePtr);

void XVit_block_top_Set_num_layers(XVit_block_top *InstancePtr, u32 Data);
u32 XVit_block_top_Get_num_layers(XVit_block_top *InstancePtr);
void XVit_block_top_Set_ext_weights(XVit_block_top *InstancePtr, u64 Data);
u64 XVit_block_top_Get_ext_weights(XVit_block_top *InstancePtr);

void XVit_block_top_InterruptGlobalEnable(XVit_block_top *InstancePtr);
void XVit_block_top_InterruptGlobalDisable(XVit_block_top *InstancePtr);
void XVit_block_top_InterruptEnable(XVit_block_top *InstancePtr, u32 Mask);
void XVit_block_top_InterruptDisable(XVit_block_top *InstancePtr, u32 Mask);
void XVit_block_top_InterruptClear(XVit_block_top *InstancePtr, u32 Mask);
u32 XVit_block_top_InterruptGetEnabled(XVit_block_top *InstancePtr);
u32 XVit_block_top_InterruptGetStatus(XVit_block_top *InstancePtr);

#ifdef __cplusplus
}
#endif

#endif
