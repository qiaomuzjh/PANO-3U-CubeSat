/**
 * PANO-3U - 姿态控制 (纯磁控)
 * 策略:
 *   阶段1 DETUMBLE: B-dot消旋, 目标 |ω| < 2 deg/s
 *   阶段2 IDLE: 维持慢自旋 1~2 deg/s (全景任务无需精确指向)
 * 执行器: 3轴磁力矩器 (DRV8837 PWM驱动, 最大磁矩 0.2 Am²/轴)
 * 敏感器: QMC5883L磁强计(主), MPU9250陀螺(辅助)
 */
#include "adcs.h"
#include "main.h"
#include "qmc5883l.h"
#include "mpu9250.h"
#include "drv8837.h"

#define BDOT_GAIN      0.5f     /* 磁矩增益 Am² per (uT/s) */
#define MAG_DIP_MAX    0.2f     /* 单轴最大磁矩 Am² */
#define DETUMBLE_TGT   2.0f     /* 目标角速度 deg/s */
#define DT             0.1f     /* 控制周期 10Hz */

static adcs_state_t state = ADCS_INIT;
static float mtq_duty[3] = {0, 0, 0};

void adcs_init(void)
{
    qmc5883l_init();
    mpu9250_init();
    drv8837_init();
    state = ADCS_DETUMBLE;
}

/* 传感器读取 (task_hk调用, 1Hz) */
void adcs_read_sensors(void)
{
    qmc5883l_read(g_sat.mag);
    mpu9250_read_gyro(g_sat.gyro);
}

/**
 * B-dot 算法: m = -K * dB/dt
 * 物理意义: 产生与磁场变化率相反的磁矩, 消耗转动动能
 */
static void bdot_step(void)
{
    float db[3];
    for (int i = 0; i < 3; i++) {
        db[i] = (g_sat.mag[i] - g_sat.mag_prev[i]) / DT;
        g_sat.mag_prev[i] = g_sat.mag[i];
        /* 磁矩指令 = -K * dB/dt, 限幅 */
        float m = -BDOT_GAIN * db[i];
        if (m >  MAG_DIP_MAX) m =  MAG_DIP_MAX;
        if (m < -MAG_DIP_MAX) m = -MAG_DIP_MAX;
        mtq_duty[i] = m / MAG_DIP_MAX;   /* -1..+1, 符号=电流方向 */
    }
}

/* 消旋完成判定: 三轴角速度均低于阈值 */
static bool detumbled(void)
{
    for (int i = 0; i < 3; i++)
        if (g_sat.gyro[i] > DETUMBLE_TGT || g_sat.gyro[i] < -DETUMBLE_TGT)
            return false;
    return true;
}

void task_adcs(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        switch (state) {
        case ADCS_DETUMBLE:
            bdot_step();
            if (detumbled()) {
                state = ADCS_MISSION;    /* 进入任务态: 磁力矩器仅补偿扰动 */
                for (int i = 0; i < 3; i++) mtq_duty[i] = 0;
            }
            break;
        case ADCS_MISSION:
            /* 任务态: 弱B-dot保持慢自旋, 防止扰动累积 */
            bdot_step();
            for (int i = 0; i < 3; i++) mtq_duty[i] *= 0.3f;
            break;
        default:
            state = ADCS_DETUMBLE;
            break;
        }
        /* 输出到DRV8837: duty<0 反向 */
        for (int i = 0; i < 3; i++)
            drv8837_set(i, mtq_duty[i]);
        vTaskDelayUntil(&last, pdMS_TO_TICKS((TickType_t)(DT * 1000)));
    }
}

adcs_state_t adcs_get_state(void) { return state; }
