/**
 * PANO-3U - DRV8837 磁力矩器驱动 / 看门狗 / 日志(W25Q128)
 */
#include "main.h"

extern TIM_HandleTypeDef htim1;
/* TIM1: CH1=PE9(X), CH2=PE11(Y), CH3=PE13(Z), 100kHz PWM */

void drv8837_init(void)
{
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_1);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_2);
    HAL_TIM_PWM_Start(&htim1, TIM_CHANNEL_3);
}

/* duty: -1.0~+1.0, 符号=方向(H桥换向由IN2控制, 简化单端+方向位) */
void drv8837_set(int ch, float duty)
{
    uint32_t arr = __HAL_TIM_GET_AUTORELOAD(&htim1);
    uint32_t ccr = (uint32_t)((duty < 0 ? -duty : duty) * arr);
    switch (ch) {
    case 0: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_1, ccr); break;
    case 1: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_2, ccr); break;
    case 2: __HAL_TIM_SET_COMPARE(&htim1, TIM_CHANNEL_3, ccr); break;
    }
    /* 方向脚: 各DRV8837 IN2接GPIO (原理图简化: 反向时IN2高,IN1 PWM反相) */
}

/* ---- 看门狗: TPS3823, PB0翻转喂狗 ---- */
void wdt_kick(void)
{
    HAL_GPIO_TogglePin(GPIOB, GPIO_PIN_0);
}

/* ---- 环形日志: W25Q128, 每记录16B ---- */
#define LOG_START_SECTOR  2048   /* 前8MB留给固件镜像 */
typedef struct { uint32_t epoch; uint8_t code; uint8_t data[8]; uint8_t pad[3]; } LogRec_t;
static uint32_t log_ptr = 0;

void log_init(void) { /* 读Flash头找写指针, 实现在w25q128.c */ }
void log_event(uint8_t code, uint32_t data)
{
    LogRec_t r; r.epoch = g_sat.uptime_s; r.code = code;
    *(uint32_t *)r.data = data; r.pad[0] = 0xAA;
    /* w25q128_write(LOG_START_SECTOR*4096 + log_ptr, &r, 16); */
    log_ptr = (log_ptr + 16) % (8 * 1024 * 1024);   /* 8MB环形 */
}
void log_get_bootcount(uint32_t *c) { *c = 0; /* w25q128读固定扇区 */ }
void log_set_bootcount(uint32_t c)  { (void)c; }
