#ifndef LINK_PROTO_H
#define LINK_PROTO_H
#include <stdint.h>
#include <stdbool.h>
#define CMD_PING 0x01
#define CMD_TIME 0x02
#define CMD_SHOOT 0x03
#define CMD_VID_START 0x04
#define CMD_VID_STOP 0x05
#define CMD_STATUS 0x07
#define RSP_ACK 0x81
#define RSP_STATUS 0x87
#define RSP_FPREP 0x89
typedef void (*link_cb)(uint8_t cmd, const uint8_t *pl, uint8_t len);
typedef struct { uint8_t buf[264]; uint16_t n; bool esc; link_cb cb; } LinkDec_t;
uint16_t link_crc16(const uint8_t *d, uint16_t n);
uint16_t link_encode(uint8_t *out, uint8_t cmd, const uint8_t *pl, uint8_t len);
void link_dec_init(LinkDec_t *d, link_cb cb);
void link_dec_feed(LinkDec_t *d, uint8_t b);
#endif
