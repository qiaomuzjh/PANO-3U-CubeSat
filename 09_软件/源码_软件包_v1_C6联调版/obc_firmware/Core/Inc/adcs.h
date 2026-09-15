#ifndef ADCS_H
#define ADCS_H
#include <stdbool.h>
typedef enum { ADCS_INIT, ADCS_DETUMBLE, ADCS_MISSION } adcs_state_t;
void adcs_init(void); void adcs_read_sensors(void); adcs_state_t adcs_get_state(void);
void task_adcs(void*);
#endif
