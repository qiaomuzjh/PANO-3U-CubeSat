#ifndef LOG_H
#define LOG_H
#include <stdint.h>
void log_init(void); void log_event(uint8_t code, uint32_t data);
void log_get_bootcount(uint32_t*); void log_set_bootcount(uint32_t);
#endif
