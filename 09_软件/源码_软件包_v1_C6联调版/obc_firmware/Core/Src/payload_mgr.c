/**
 * PANO-3U - 载荷管理: 与CM4的协议交互 + 拍摄计划
 */
#include "payload_mgr.h"
#include "main.h"
#include "link_proto.h"
#include "log.h"
#include "comm.h"
#include <string.h>

/* ---- 拍摄计划表 (最多32条, 存RTC备份域) ---- */
typedef struct {
    uint32_t epoch;      /* 执行时刻 */
    uint8_t  cmd;        /* 0x03=拍照 0x04=视频 0x06=延时 */
    uint16_t param1;     /* 连拍/时长 */
    uint16_t param2;     /* 间隔 */
} SchedEntry_t;

static SchedEntry_t sched[32];
static int sched_count = 0;
static bool pl_busy = false;
static uint32_t pl_last_rsp = 0;

/* ---- 链路: 帧发送 ---- */
static void pl_send(uint8_t cmd, const uint8_t *pl, uint8_t len)
{
    uint8_t frame[280];
    uint16_t n = link_encode(frame, cmd, pl, len);
    HAL_UART_Transmit(&huart2, frame, n, 100);
}

/* ---- 帧接收回调 (中断->解码器->此处) ---- */
static void on_pl_frame(uint8_t cmd, const uint8_t *pl, uint8_t len)
{
    pl_last_rsp = g_sat.uptime_s;
    switch (cmd) {
    case RSP_STATUS:
        if (len >= 12) {
            g_sat.pl_mode    = pl[0];
            g_sat.pl_err     = pl[len - 7];   /* last_err字段偏移 */
            g_sat.pl_online  = true;
            if (pl[0] == 0) pl_busy = false;  /* IDLE */
        }
        break;
    case RSP_FPREP: {
        /* CM4备好文件: 加入下行队列 */
        if (len >= 12) {
            uint32_t fid; uint16_t total;
            memcpy(&fid, &pl[0], 4); memcpy(&total, &pl[4], 2);
            comm_queue_file(fid, total);
        }
        break; }
    case RSP_ACK:
    default:
        break;
    }
}

void payload_mgr_init(void)
{
    payload_power(true);           /* 默认给载荷上电 */
    sched_count = 0;
}

/* 1Hz轮询: 心跳 + 计划检查 */
void payload_mgr_step(void)
{
    static uint32_t last_ping = 0;
    if (g_sat.uptime_s - last_ping >= 1) {
        pl_send(CMD_PING, NULL, 0);
        last_ping = g_sat.uptime_s;
    }
    /* 链路健康: 60s无应答 -> 重启载荷电源 */
    if (g_sat.uptime_s - pl_last_rsp > 60 && g_sat.mode == MODE_PAYLOAD) {
        payload_power(false);
        HAL_Delay(500);
        payload_power(true);
        log_event(EVT_ERROR, ERR_LINK_TIMEOUT);
        pl_last_rsp = g_sat.uptime_s;
    }
}

/* ---- 计划调度 ---- */
int schedule_add(uint32_t epoch, uint8_t cmd, uint16_t p1, uint16_t p2)
{
    if (sched_count >= 32) return -1;
    sched[sched_count] = (SchedEntry_t){epoch, cmd, p1, p2};
    sched_count++;
    return 0;
}

bool schedule_due(void)
{
    if (sched_count == 0 || pl_busy) return false;
    uint32_t now = rtc_epoch();
    for (int i = 0; i < sched_count; i++)
        if (sched[i].epoch <= now) return true;
    return false;
}

void payload_run_scheduled(void)
{
    uint32_t now = rtc_epoch();
    for (int i = 0; i < sched_count; i++) {
        if (sched[i].epoch <= now) {
            uint8_t pl[4];
            switch (sched[i].cmd) {
            case 0x03:  /* 拍照 */
                pl[0] = (uint8_t)sched[i].param1;
                pl[1] = sched[i].param2 & 0xFF; pl[2] = sched[i].param2 >> 8;
                pl_send(CMD_SHOOT, pl, 3);
                log_event(EVT_SHOOT, sched[i].param1);
                break;
            case 0x04:  /* 视频 */
                pl[0] = sched[i].param1 & 0xFF; pl[1] = sched[i].param1 >> 8;
                pl[2] = 30;
                pl_send(CMD_VID_START, pl, 3);
                log_event(EVT_VIDEO, sched[i].param1);
                break;
            }
            /* 移除已执行条目 */
            memmove(&sched[i], &sched[i + 1], (sched_count - i - 1) * sizeof(SchedEntry_t));
            sched_count--;
            i--;
            pl_busy = true;
        }
    }
}

bool payload_done(void) { return !pl_busy; }

/* 供comm.c读文件块: 通过UART向CM4请求 */
uint16_t payload_read_chunk(uint32_t fid, uint16_t chunk_no, uint8_t *out)
{
    /* 请求-应答: 实际为异步, 此处简化同步等待 (超时200ms) */
    uint8_t req[6];
    memcpy(req, &fid, 4); memcpy(req + 4, &chunk_no, 2);
    pl_send(0x0B, req, 6);     /* CMD_FILE_CHUNK (协议扩展) */
    /* 等待RSP_CHUNK... 实际实现用信号量 */
    return 0;   /* 占位: 完整实现见link_proto.c异步状态机 */
}

void task_payload(void *arg)
{
    for (;;) {
        payload_mgr_step();
        obc_fsm_step();
        vTaskDelay(pdMS_TO_TICKS(1000));
    }
}
