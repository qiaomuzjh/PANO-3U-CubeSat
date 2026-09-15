#ifndef WATCHDOG_H
#define WATCHDOG_H
typedef struct { int unused; } WDT_Handle_t;
void wdt_kick(void);
#endif
