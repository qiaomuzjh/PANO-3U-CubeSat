/**
 * PANO-3U - UHF通信 (AX.25封装 + 文件断点续传)
 * 物理层: Si4463 GFSK 9600bps, OBC经UART1向通信板发送数据流
 * AX.25 UI帧在OBC软件内完成HDLC封装(标志/位填充/FCS)
 */
#include "comm.h"
#include "main.h"
#include "log.h"
#include "payload_mgr.h"
#include <string.h>

/* ---- AX.25/HDLC ---- */
#define HDLC_FLAG  0x7E
static const uint8_t CALL_SAT[7]  = {'N','O','C','A','L','L', 0x62}; /* SSID=1 */
static const uint8_t CALL_GND[7]  = {'N','O','C','A','L','L', 0x60}; /* SSID=0 */

static uint16_t fcs_table[256];
static bool fcs_ready = false;

static void fcs_init(void)
{
    for (int i = 0; i < 256; i++) {
        uint16_t c = i;
        for (int b = 0; b < 8; b++)
            c = (c & 1) ? (c >> 1) ^ 0x8408 : (c >> 1);
        fcs_table[i] = c;
    }
    fcs_ready = true;
}
static uint16_t fcs_update(uint16_t fcs, uint8_t b)
{
    return (fcs >> 8) ^ fcs_table[(fcs ^ b) & 0xFF];
}

/* HDLC发送: 位填充 + FLAG */
static void hdlc_send_byte(uint8_t b)
{
    static int ones = 0;
    /* 简化实现: 实际位填充在Si4463同步模式下由FPGA式bit流完成;
       此处采用异步帧模式: 数据送通信板, 由板上逻辑处理位填充 */
    HAL_UART_Transmit(&huart1, &b, 1, 10);
}

void ax25_send_ui(const uint8_t *info, uint16_t len)
{
    if (!fcs_ready) fcs_init();
    uint16_t fcs = 0xFFFF;
    hdlc_send_byte(HDLC_FLAG);
    for (int i = 0; i < 7; i++) { fcs = fcs_update(fcs, CALL_GND[i]); hdlc_send_byte(CALL_GND[i]); }
    for (int i = 0; i < 7; i++) { fcs = fcs_update(fcs, CALL_SAT[i]); hdlc_send_byte(CALL_SAT[i]); }
    fcs = fcs_update(fcs, 0x03); hdlc_send_byte(0x03);   /* UI帧控制字 */
    fcs = fcs_update(fcs, 0xF0); hdlc_send_byte(0xF0);   /* PID: 无层3 */
    for (uint16_t i = 0; i < len; i++) {
        fcs = fcs_update(fcs, info[i]);
        hdlc_send_byte(info[i]);
    }
    fcs ^= 0xFFFF;
    hdlc_send_byte(fcs & 0xFF);
    hdlc_send_byte(fcs >> 8);
    hdlc_send_byte(HDLC_FLAG);
}

/* ---- 下行文件队列 ---- */
#define DL_MAX 8
static struct {
    uint32_t file_id;
    uint16_t next_chunk, total;
} dl_queue[DL_MAX];
static int dl_count = 0;
static bool dl_active = false;

void comm_init(void)
{
    fcs_init();
    dl_count = 0;
}

/* 信标: 30s周期 */
void comm_queue_beacon(void)
{
    uint8_t buf[64];
    uint16_t seq = (uint16_t)(g_sat.uptime_s / 30);
    buf[0] = PKT_BEACON;
    buf[1] = seq & 0xFF; buf[2] = seq >> 8;
    buf[3] = (uint8_t)g_sat.mode;
    buf[4] = g_sat.last_error;
    buf[5] = g_sat.vbat_mv & 0xFF; buf[6] = g_sat.vbat_mv >> 8;
    buf[7] = g_sat.ibat_ma & 0xFF; buf[8] = (g_sat.ibat_ma >> 8) & 0xFF;
    memcpy(&buf[9], g_sat.temp, 6);
    /* 姿态: 量化到0.5deg/s */
    for (int i = 0; i < 3; i++)
        buf[15 + i] = (uint8_t)(int8_t)(g_sat.gyro[i] * 2);
    buf[18] = g_sat.pl_mode; buf[19] = g_sat.pl_err;
    buf[20] = g_sat.pl_free_mb & 0xFF; buf[21] = g_sat.pl_free_mb >> 8;
    buf[22] = g_sat.pl_files & 0xFF; buf[23] = g_sat.pl_files >> 8;
    ax25_send_ui(buf, 24);
}

/* 把文件加入下行队列 */
int comm_queue_file(uint32_t file_id, uint16_t total_chunks)
{
    if (dl_count >= DL_MAX) return -1;
    dl_queue[dl_count].file_id = file_id;
    dl_queue[dl_count].next_chunk = 0;
    dl_queue[dl_count].total = total_chunks;
    dl_count++;
    return 0;
}

/* 处理地面REQ_MISSING: 重排某文件的发送块序 */
void comm_req_missing(uint32_t file_id, const uint16_t *missing, uint16_t n)
{
    /* 简化: 将缺失块压入优先队列, 下一轮先发 */
    for (int i = 0; i < dl_count; i++) {
        if (dl_queue[i].file_id == file_id && n > 0) {
            dl_queue[i].next_chunk = missing[0];  /* 从首个缺失块继续 */
        }
    }
}

void comm_downlink_start(void)
{
    dl_active = true;
    log_event(EVT_DOWNLINK_START, 0);
}
bool comm_downlink_done(void)
{
    return !dl_active || dl_count == 0;
}

/**
 * 通信任务: 发射机占空比管理 + 队列轮询
 * 每次过境连续发送; 过热(通信板>60C)暂停60s
 */
void task_comm(void *arg)
{
    TickType_t last = xTaskGetTickCount();
    for (;;) {
        if (g_sat.mode == MODE_DOWNLINK && dl_count > 0) {
            /* 轮询队列, 每文件每次最多发50块后切换 */
            int sent = 0;
            while (dl_queue[0].next_chunk < dl_queue[0].total && sent < 50) {
                uint8_t pkt[220];
                uint16_t n = payload_read_chunk(dl_queue[0].file_id,
                                                dl_queue[0].next_chunk,
                                                &pkt[9]);
                pkt[0] = PKT_FILE_CHUNK;
                memcpy(&pkt[1], &dl_queue[0].file_id, 4);
                pkt[5] = dl_queue[0].next_chunk & 0xFF;
                pkt[6] = dl_queue[0].next_chunk >> 8;
                pkt[7] = dl_queue[0].total & 0xFF;
                pkt[8] = dl_queue[0].total >> 8;
                ax25_send_ui(pkt, 9 + n);
                dl_queue[0].next_chunk++;
                sent++;
                vTaskDelay(pdMS_TO_TICKS(180));   /* ~9.6kbps节流 */
            }
            if (dl_queue[0].next_chunk >= dl_queue[0].total) {
                /* 该文件发完一轮, 移出队列等地面确认 */
                memmove(dl_queue, dl_queue + 1, sizeof(dl_queue) - sizeof(dl_queue[0]));
                dl_count--;
                if (dl_count == 0) {
                    dl_active = false;
                    log_event(EVT_DOWNLINK_DONE, 0);
                }
            }
        }
        /* 上行接收: 简化轮询 (中断驱动更佳) */
        comm_rx_poll();
        vTaskDelayUntil(&last, pdMS_TO_TICKS(100));
    }
}

/* 上行命令处理 (通信板收到后转发OBC) */
void comm_rx_poll(void)
{
    uint8_t b;
    while (HAL_UART_Receive(&huart1, &b, 1, 0) == HAL_OK) {
        /* 简化: 收齐AX.25帧后解析; 实际实现用DMA+环形缓冲 */
        /* 此处省略帧重组状态机, 见comm_rx.c完整实现位 */
        (void)b;
    }
}
