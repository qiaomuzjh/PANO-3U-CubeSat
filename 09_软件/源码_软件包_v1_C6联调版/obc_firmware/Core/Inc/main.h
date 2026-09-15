/**
 * PANO-3U OBC - 全局类型与共享定义
 */
#ifndef MAIN_H
#define MAIN_H

#include <stdint.h>
#include <stdbool.h>
#include "stm32f4xx_hal.h"
#include "FreeRTOS.h"
#include "task.h"

/* ---- 工作模式 ---- */
typedef enum {
    MODE_SAFE = 0,       /* 安全模式: 最小功耗, 等待地面指令 */
    MODE_DETUMBLE,       /* 消旋: 入轨后B-dot */
    MODE_IDLE,           /* 待机: 正常遥测 */
    MODE_PAYLOAD,        /* 拍摄中 */
    MODE_DOWNLINK,       /* 数传中 */
    MODE_DEPLOY,         /* 天线展开序列 */
} SatMode_t;

/* ---- 错误码 (与协议规范§3一致) ---- */
typedef enum {
    ERR_NONE = 0, ERR_CAM0, ERR_CAM1, ERR_DISK_FULL, ERR_DISK_IO,
    ERR_ENCODER, ERR_TEMP, ERR_PARAM, ERR_LINK_TIMEOUT,
    ERR_LOW_POWER, ERR_COMM, ERR_WATCHDOG_RESET,
} ErrCode_t;

/* ---- 日志事件码 ---- */
typedef enum {
    EVT_BOOT = 0x01, EVT_MODE_CHANGE, EVT_LOW_POWER, EVT_DEPLOY,
    EVT_SHOOT, EVT_VIDEO, EVT_DOWNLINK_START, EVT_DOWNLINK_DONE,
    EVT_CMD_RX, EVT_ERROR,
} EvtCode_t;

/* ---- 全局卫星状态 ---- */
typedef struct {
    SatMode_t mode;
    uint32_t  uptime_s;
    uint32_t  boot_count;
    uint8_t   last_error;
    /* ADCS */
    float mag[3];        /* 磁场 uT */
    float gyro[3];       /* 角速度 deg/s */
    float mag_prev[3];
    /* 电源 */
    uint16_t vbat_mv;
    int16_t  ibat_ma;
    uint16_t v5_mv, i5_ma;
    /* 温度 x6: 电池0/1, 相机0/1, OBC板, EPS板 */
    int8_t   temp[6];
    /* 载荷状态缓存 (CM4 STATUS帧) */
    uint8_t  pl_mode, pl_err;
    uint16_t pl_free_mb, pl_files;
    bool     pl_online;
} SatState_t;

extern SatState_t g_sat;

/* 各模块接口 */
void MX_GPIO_Init(void); void MX_I2C1_Init(void); void MX_I2C2_Init(void);
void MX_SPI2_Init(void); void MX_USART1_Init(void); void MX_USART2_Init(void);
void MX_TIM1_PWM_Init(void); void MX_ADC_Init(void);
void task_hk(void *); void task_adcs(void *); void task_comm(void *); void task_payload(void *);
void power_guard(void); void heater_force(bool on); void antenna_deploy(void);
void thermal_update(void);

/* 载荷电源开关: PAYLOAD_EN -> EPS TPS2553 -> CM4 5V */
static inline void payload_power(bool on) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_7, on ? GPIO_PIN_SET : GPIO_PIN_RESET);
}
static inline void heater_force(bool on) {
    HAL_GPIO_WritePin(GPIOA, GPIO_PIN_0, on ? GPIO_PIN_SET : GPIO_PIN_RESET);
}

#endif
