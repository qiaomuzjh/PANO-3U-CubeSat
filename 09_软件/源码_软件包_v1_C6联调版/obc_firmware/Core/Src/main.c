/**
 * PANO-3U OBC 固件 - 主程序
 * MCU: STM32F405RGT6 @168MHz, HAL库
 * 任务: 遥测采集 / 模式管理 / 姿态控制(B-dot) / 载荷调度 / UHF通信
 * RTOS: FreeRTOS
 */
#include "main.h"
#include "obc_fsm.h"
#include "adcs.h"
#include "comm.h"
#include "eps_mon.h"
#include "payload_mgr.h"
#include "watchdog.h"
#include "log.h"

/* HAL 句柄 (CubeMX生成部分略, 此处声明) */
I2C_HandleTypeDef  hi2c1, hi2c2;
SPI_HandleTypeDef  hspi2;
UART_HandleTypeDef huart1;   /* 通信板 */
UART_HandleTypeDef huart2;   /* CM4载荷 */
TIM_HandleTypeDef  htim1;    /* PWM: 磁力矩器 XYZ */
WDT_Handle_t       hwdt;

/* 全局状态 */
SatState_t g_sat = {
    .mode = MODE_SAFE,
    .uptime_s = 0,
    .boot_count = 0,
    .last_error = ERR_NONE,
    .mag = {0}, .gyro = {0},
    .vbat_mv = 0, .ibat_ma = 0,
    .temp = {25,25,25,25,25,25},
};

/* FreeRTOS 任务 */
static TaskHandle_t h_task_hk, h_task_adcs, h_task_comm, h_task_pl;

void SystemClock_Config(void);  /* CubeMX生成: HSE 8M -> PLL -> 168M */

int main(void)
{
    HAL_Init();
    SystemClock_Config();

    /* 外设初始化 */
    MX_GPIO_Init();       /* 含分离开关/天线状态GPIO */
    MX_I2C1_Init();       /* INA226/IMU/磁强计 */
    MX_I2C2_Init();       /* DS3231 RTC */
    MX_SPI2_Init();       /* W25Q128 */
    MX_USART1_Init();     /* 通信板 9600 */
    MX_USART2_Init();     /* CM4 115200 */
    MX_TIM1_PWM_Init();   /* 磁力矩器驱动 */
    MX_ADC_Init();        /* 备份电压采集 */

    log_init();           /* W25Q128环形日志 */
    uint32_t boot = 0;
    log_get_bootcount(&boot);
    g_sat.boot_count = boot + 1;
    log_set_bootcount(g_sat.boot_count);
    log_event(EVT_BOOT, g_sat.boot_count);

    /* 入轨延时: CDS要求分离后30分钟才能发射RF/展开机构 */
    if (g_sat.boot_count <= 2) {   /* 仅入轨初期执行 */
        HAL_Delay(30U * 60U * 1000U);
        antenna_deploy();          /* 热刀释放天线 */
    }

    obc_fsm_init();
    adcs_init();
    comm_init();
    payload_mgr_init();

    /* 任务创建: 优先级 高->低 = 通信 > ADCS >  housekeeping > 载荷 */
    xTaskCreate(task_comm,    "comm", 1024, NULL, 4, &h_task_comm);
    xTaskCreate(task_adcs,    "adcs",  768, NULL, 3, &h_task_adcs);
    xTaskCreate(task_hk,      "hk",   1024, NULL, 2, &h_task_hk);
    xTaskCreate(task_payload, "pl",   1536, NULL, 1, &h_task_pl);

    vTaskStartScheduler();
    while (1);   /* 不应到达 */
}

/**
 * 内务任务: 1Hz 遥测采集 + 看门狗喂狗 + 电池保护
 */
void task_hk(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        eps_mon_update();        /* INA226 x4 -> g_sat.vbat_mv 等 */
        adcs_read_sensors();     /* IMU + 磁强计 */
        thermal_update();        /* DS18B20 x6 -> 加热片控制 */
        power_guard();           /* 低压 -> SAFE模式 */

        wdt_kick();              /* 喂 TPS3823 (PA0翻转->实际是专用GPIO) */

        if ((g_sat.uptime_s % 30) == 0)
            comm_queue_beacon(); /* 30s信标 */

        g_sat.uptime_s++;
        vTaskDelayUntil(&last, pdMS_TO_TICKS(1000));
    }
}

/* 电池低压保护: VBAT<6.6V 进SAFE, 关载荷 */
void power_guard(void)
{
    if (g_sat.vbat_mv > 0 && g_sat.vbat_mv < 6600 && g_sat.mode != MODE_SAFE) {
        log_event(EVT_LOW_POWER, g_sat.vbat_mv);
        payload_power(false);    /* 断PAYLOAD_EN */
        heater_force(false);
        obc_set_mode(MODE_SAFE);
    }
}
