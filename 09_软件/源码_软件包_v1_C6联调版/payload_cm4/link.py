"""OBC<->CM4 链路层: HDLC风格帧 + CRC16-CCITT
帧: [0x7E][CMD][LEN][PAYLOAD][CRC16_lo][CRC16_hi][0x7E], 0x7D转义
"""
import struct

FLAG = 0x7E
ESC = 0x7D

# 指令码 (OBC->CM4)
CMD_PING, CMD_TIME, CMD_SHOOT = 0x01, 0x02, 0x03
CMD_VID_START, CMD_VID_STOP, CMD_TIMELAPSE = 0x04, 0x05, 0x06
CMD_STATUS, CMD_FLIST, CMD_FPREP, CMD_SHUTDOWN = 0x07, 0x08, 0x09, 0x0A
CMD_PARAM = 0x10
# 应答码 (CM4->OBC)
RSP_ACK, RSP_STATUS, RSP_FLIST, RSP_FPREP = 0x81, 0x87, 0x88, 0x89


def crc16(data: bytes) -> int:
    crc = 0xFFFF
    for b in data:
        crc ^= b << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def encode(cmd: int, payload: bytes = b"") -> bytes:
    body = bytes([cmd, len(payload)]) + payload
    frame = body + struct.pack("<H", crc16(body))
    out = bytearray([FLAG])
    for b in frame:
        if b in (FLAG, ESC):
            out += bytes([ESC, b ^ 0x20])
        else:
            out.append(b)
    out.append(FLAG)
    return bytes(out)


class Decoder:
    """流式解码器: 逐字节feed, 收满一帧回调"""
    def __init__(self, on_frame):
        self.buf = bytearray()
        self.in_frame = False
        self.esc = False
        self.on_frame = on_frame

    def feed(self, data: bytes):
        for b in data:
            if b == FLAG:
                if self.in_frame and len(self.buf) >= 4:
                    self._emit()
                self.buf = bytearray(); self.in_frame = True; self.esc = False
            elif not self.in_frame:
                continue
            elif b == ESC:
                self.esc = True
            elif self.esc:
                self.buf.append(b ^ 0x20); self.esc = False
            else:
                self.buf.append(b)
                if len(self.buf) > 260:
                    self.buf = bytearray(); self.in_frame = False

    def _emit(self):
        raw = bytes(self.buf)
        body, got = raw[:-2], struct.unpack("<H", raw[-2:])[0]
        if crc16(body) == got:
            self.on_frame(body[0], body[2:2 + body[1]])
        # CRC错帧静默丢弃 (链路层重试由上层超时处理)


class UartLink:
    """CM4侧: 串口收发线程"""
    def __init__(self, port, baud, on_cmd):
        import serial
        self.ser = serial.Serial(port, baud, timeout=0.1)
        self.dec = Decoder(on_cmd)
        self.on_cmd = on_cmd

    def send(self, cmd, payload=b""):
        self.ser.write(encode(cmd, payload))

    def poll(self):
        data = self.ser.read(256)
        if data:
            self.dec.feed(data)
