#ifndef COMM_H
#define COMM_H
#include <stdint.h>
#include <stdbool.h>
#define PKT_BEACON 0x01
#define PKT_FILE_CHUNK 0x02
#define PKT_FLIST 0x03
#define PKT_EVENT 0x04
void comm_init(void); void comm_queue_beacon(void);
int  comm_queue_file(uint32_t file_id, uint16_t total_chunks);
void comm_downlink_start(void); bool comm_downlink_done(void);
bool comm_pass_predicted(void); void comm_rx_poll(void); void task_comm(void*);
#endif
