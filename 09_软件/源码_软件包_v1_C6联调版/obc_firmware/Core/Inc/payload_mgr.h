#ifndef PAYLOAD_MGR_H
#define PAYLOAD_MGR_H
#include <stdint.h>
#include <stdbool.h>
void payload_mgr_init(void); void payload_mgr_step(void);
int  schedule_add(uint32_t epoch, uint8_t cmd, uint16_t p1, uint16_t p2);
bool schedule_due(void); void payload_run_scheduled(void); bool payload_done(void);
uint16_t payload_read_chunk(uint32_t fid, uint16_t chunk_no, uint8_t *out);
void task_payload(void*);
#endif
