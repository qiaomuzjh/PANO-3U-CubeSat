"""地面站接收机: 对接 Direwolf (soundmodem) 或 GQRX+UDP
Direwolf以KISS TCP(默认8001)输出解调后的AX.25帧, 本模块负责解析
"""
import socket, struct, threading, time

KISS_FEND = 0xC0

class KissReceiver:
    def __init__(self, host="127.0.0.1", port=8001):
        self.sock = socket.create_connection((host, port))
        self.handlers = []

    def on_packet(self, cb): self.handlers.append(cb)

    def run(self):
        buf = bytearray(); esc = False; in_f = False
        while True:
            data = self.sock.recv(4096)
            if not data: raise ConnectionError("direwolf closed")
            for b in data:
                if b == KISS_FEND:
                    if in_f and len(buf) > 1: self._handle(bytes(buf[1:]))
                    buf = bytearray(); in_f = True; esc = False
                elif in_f:
                    if b == 0xDB: esc = True
                    elif esc: buf.append(b ^ 0x20); esc = False
                    else: buf.append(b)

    def _handle(self, frame):
        pkt = parse_ax25(frame)
        if pkt:
            for cb in self.handlers: cb(pkt)


def parse_ax25(frame: bytes):
    """解析AX.25 UI帧 -> (src, dst, payload)"""
    if len(frame) < 18: return None
    dst = bytes(b >> 1 for b in frame[0:6]).decode("ascii", "replace").strip()
    src = bytes(b >> 1 for b in frame[7:13]).decode("ascii", "replace").strip()
    if frame[14] != 0x03 or frame[15] != 0xF0: return None
    # KISS TCP 模式 (direwolf 等) 给出的帧已剥离 FCS, 载荷为 frame[16:];
    # 若对接含 FCS 的原始帧, 改回 frame[16:-2]
    payload = frame[16:]
    return {"src": src, "dst": dst, "payload": payload, "ts": time.time()}


# 下行包类型 (与协议规范§2一致)
PKT_BEACON, PKT_CHUNK, PKT_FLIST, PKT_EVENT = 0x01, 0x02, 0x03, 0x04

def parse_downlink(payload: bytes):
    t = payload[0]
    if t == PKT_BEACON and len(payload) >= 24:
        return {"type": "beacon", "seq": struct.unpack("<H", payload[1:3])[0],
                "mode": payload[3], "err": payload[4],
                "vbat_mv": struct.unpack("<H", payload[5:7])[0],
                "ibat_ma": struct.unpack("<h", payload[7:9])[0],
                "temp": list(struct.unpack("6b", payload[9:15])),
                "gyro_dps": [b / 2 for b in struct.unpack("3b", payload[15:18])],
                "pl_mode": payload[18], "pl_err": payload[19],
                "free_mb": struct.unpack("<H", payload[20:22])[0],
                "files": struct.unpack("<H", payload[22:24])[0]}
    if t == PKT_CHUNK and len(payload) >= 9:
        return {"type": "chunk",
                "file_id": struct.unpack("<I", payload[1:5])[0],
                "chunk_no": struct.unpack("<H", payload[5:7])[0],
                "total": struct.unpack("<H", payload[7:9])[0],
                "data": payload[9:]}
    return {"type": f"unknown_{t}"}
