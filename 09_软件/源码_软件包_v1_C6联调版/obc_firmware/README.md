# OBC 固件构建说明

## 工具链
- STM32CubeMX 6.x (生成HAL骨架) + arm-none-eabi-gcc
- 或 PlatformIO: `platform = ststm32`, `board = genericSTM32F405RG`

## 目录
```
Core/Src/
  main.c          主程序+任务
  obc_fsm.c       模式状态机
  adcs.c          B-dot消旋
  comm.c          AX.25+下行队列
  payload_mgr.c   CM4协议+拍摄计划
  link_proto.c    板间帧编解码
  drivers.c       QMC5883L/MPU9250/INA226/DS18B20/热控/天线
  misc_drivers.c  DRV8837/看门狗/W25Q128日志
Core/Inc/         对应头文件 (位号/寄存器地址与电子系统规格书一致)
```

## 构建
```bash
# CubeMX方式: 用 PANO-3U.ioc 生成工程后替换Core/Src
arm-none-eabi-gcc -mcpu=cortex-m4 -mthumb -mfpu=fpv4-sp-d16 -mfloat-abi=hard \
  -O2 -DUSE_HAL_DRIVER -DSTM32F405xx ...
# PlatformIO方式:
pio run -e obc
```

## 关键配置
- FreeRTOS: 4任务 (comm>adcs>hk>payload), 堆栈见main.c
- HSE 8MHz → PLL → 168MHz, SysTick 1kHz
- UART1=9600(通信板), UART2=115200(CM4), 均DMA+空闲中断
- Flash: 前64KB bootloader(预留IAP), 应用从0x08010000
