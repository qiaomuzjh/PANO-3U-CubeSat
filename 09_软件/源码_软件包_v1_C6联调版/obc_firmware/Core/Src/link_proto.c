/**
 * 板间链路协议 (与 payload_cm4/link.py 对应)
 * 帧: [0x7E][CMD][LEN][PAYLOAD][CRC16-CCITT LE][0x7E], 0x7D转义
 */
#include "link_proto.h"

uint16_t link_crc16(const uint8_t *d, uint16_t n)
{
    uint16_t crc = 0xFFFF;
    while (n--) {
        crc ^= (uint16_t)(*d++) << 8;
        for (int i = 0; i < 8; i++)
            crc = (crc & 0x8000) ? (crc << 1) ^ 0x1021 : crc << 1;
    }
    return crc;
}

uint16_t link_encode(uint8_t *out, uint8_t cmd, const uint8_t *pl, uint8_t len)
{
    uint8_t body[260];
    body[0] = cmd; body[1] = len;
    for (uint8_t i = 0; i < len; i++) body[2 + i] = pl[i];
    uint16_t crc = link_crc16(body, len + 2);
    body[len + 2] = crc & 0xFF; body[len + 3] = crc >> 8;
    uint16_t o = 0;
    out[o++] = 0x7E;
    for (uint16_t i = 0; i < (uint16_t)(len + 4); i++) {
        if (body[i] == 0x7E || body[i] == 0x7D) {
            out[o++] = 0x7D; out[o++] = body[i] ^ 0x20;
        } else out[o++] = body[i];
    }
    out[o++] = 0x7E;
    return o;
}

void link_dec_init(LinkDec_t *d, link_cb cb) { d->n = 0; d->esc = false; d->cb = cb; }

void link_dec_feed(LinkDec_t *d, uint8_t b)
{
    if (b == 0x7E) {
        if (d->n >= 4) {
            uint16_t got = d->buf[d->n - 2] | (d->buf[d->n - 1] << 8);
            if (link_crc16(d->buf, d->n - 2) == got)
                d->cb(d->buf[0], &d->buf[2], d->buf[1]);
        }
        d->n = 0; d->esc = false;
        return;
    }
    if (b == 0x7D) { d->esc = true; return; }
    if (d->esc) { b ^= 0x20; d->esc = false; }
    if (d->n < sizeof(d->buf)) d->buf[d->n++] = b;
    else d->n = 0;   /* 溢出丢帧 */
}
