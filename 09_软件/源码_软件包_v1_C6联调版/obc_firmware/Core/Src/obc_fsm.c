/**
 * PANO-3U - 工作模式状态机
 */
#include "obc_fsm.h"
#include "main.h"
#include "payload_mgr.h"
#include "comm.h"
#include "log.h"

static SatMode_t mode_prev = MODE_SAFE;

void obc_set_mode(SatMode_t m)
{
    if (m == g_sat.mode) return;
    mode_prev = g_sat.mode;
    g_sat.mode = m;
    log_event(EVT_MODE_CHANGE, (uint32_t)m);
    /* 模式进入动作 */
    switch (m) {
    case MODE_SAFE:
        payload_power(false);
        break;
    case MODE_DOWNLINK:
        comm_downlink_start();
        break;
    case MODE_PAYLOAD:
        payload_power(true);
        break;
    default: break;
    }
}

void obc_fsm_init(void)
{
    /* 首次上电: 先消旋 */
    obc_set_mode(MODE_DETUMBLE);
}

/**
 * 状态机主循环 (task_hk中1Hz调用或独立任务)
 * 转换逻辑:
 *   DETUMBLE --(消旋完成)--> IDLE
 *   IDLE --(计划表到点)--> PAYLOAD
 *   IDLE --(过境窗口)--> DOWNLINK
 *   PAYLOAD --(完成)--> IDLE
 *   any --(低压/故障)--> SAFE --(地面指令)--> IDLE
 */
void obc_fsm_step(void)
{
    switch (g_sat.mode) {
    case MODE_DETUMBLE:
        if (adcs_get_state() == ADCS_MISSION)
            obc_set_mode(MODE_IDLE);
        break;
    case MODE_IDLE:
        if (schedule_due()) {                     /* 有拍摄计划到点 */
            obc_set_mode(MODE_PAYLOAD);
            payload_run_scheduled();
        } else if (comm_pass_predicted()) {       /* 过境窗口 */
            obc_set_mode(MODE_DOWNLINK);
        }
        break;
    case MODE_PAYLOAD:
        if (payload_done())
            obc_set_mode(MODE_IDLE);
        break;
    case MODE_DOWNLINK:
        if (comm_downlink_done())
            obc_set_mode(MODE_IDLE);
        break;
    case MODE_SAFE:
        /* 仅地面指令或电源恢复后超时自动恢复 */
        if (g_sat.vbat_mv > 7000 && g_sat.uptime_s > 600)
            obc_set_mode(MODE_IDLE);
        break;
    default:
        obc_set_mode(MODE_SAFE);
    }
}
