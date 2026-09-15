"""PANO-3U 载荷主程序 (CM4)
状态机: BOOT -> IDLE -> (SHOOTING | RECORDING | TIMELAPSE) -> IDLE -> SHUTDOWN
运行: python3 main.py  (systemd服务 pano3u-payload.service)
"""
import os, time, threading, struct, signal, sys
from config import cfg
from camera import DualFisheyeCamera, ON_TARGET
from storage import StorageManager
from stitch import PanoStitcher
import link as L
import cv2
import numpy as np

MODE_IDLE, MODE_SHOOTING, MODE_RECORDING, MODE_TIMELAPSE = 0, 1, 2, 3


class PayloadApp:
    def __init__(self):
        self.mode = MODE_IDLE
        self.last_err = 0
        self.cam = DualFisheyeCamera(cfg)
        self.store = StorageManager(cfg)
        self.stitcher = None
        calib = os.path.join(os.path.dirname(__file__), cfg["calib_file"])
        if os.path.exists(calib):
            self.stitcher = PanoStitcher(calib, cfg["pano_width"], cfg["pano_height"])
        self.last_ping = time.time()
        self.video_deadline = None
        self.timelapse = None
        self._stop = False
        if ON_TARGET:
            self.link = L.UartLink(cfg["uart_port"], cfg["uart_baud"], self.on_cmd)
        else:
            self.link = None

    # ---------------- 指令处理 ----------------
    def on_cmd(self, cmd, pl):
        if cmd == L.CMD_PING:
            self.last_ping = time.time()
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
        elif cmd == L.CMD_TIME and len(pl) == 4:
            epoch = struct.unpack("<I", pl)[0]
            if ON_TARGET:
                os.system(f"date -s @{epoch}")
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
        elif cmd == L.CMD_SHOOT and len(pl) >= 3:
            burst, interval = pl[0], struct.unpack("<H", pl[1:3])[0]
            threading.Thread(target=self._shoot_task, args=(burst, interval), daemon=True).start()
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
        elif cmd == L.CMD_VID_START and len(pl) >= 3:
            dur, _fps = struct.unpack("<H", pl[:2])[0], pl[2]
            self._start_video(min(dur, cfg["video_max_duration_s"]))
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
        elif cmd == L.CMD_VID_STOP:
            self._stop_video()
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
        elif cmd == L.CMD_STATUS:
            self.link.send(L.RSP_STATUS, self._status())
        elif cmd == L.CMD_FLIST:
            off = struct.unpack("<H", pl[:2])[0] if len(pl) >= 2 else 0
            files = self.store.list_files(off)
            body = struct.pack("<H", len(files))
            for fid, size, ts, kind in files:
                body += struct.pack("<III", fid, size, ts) + kind.encode()[:8].ljust(8, b"\0")
            self.link.send(L.RSP_FLIST, body)
        elif cmd == L.CMD_FPREP and len(pl) == 4:
            fid = struct.unpack("<I", pl)[0]
            info = self.store.prep_file(fid)
            if info:
                self.link.send(L.RSP_FPREP, struct.pack("<IHHI",
                    info["file_id"], info["total"], info["chunk_size"], info["crc32"]))
            else:
                self.link.send(L.RSP_ACK, bytes([cmd, 3]))   # err: 存储
        elif cmd == L.CMD_PARAM and len(pl) >= 5:
            keymap = {1: ("ae_exposure_us", "<I"), 2: ("analogue_gain", "<f"),
                      3: ("video_bitrate_mbps", "<I"), 4: ("jpeg_quality", "<I")}
            k, fmt = keymap.get(pl[0], (None, None))
            if k:
                cfg.set(k, struct.unpack(fmt, pl[1:1 + struct.calcsize(fmt)])[0])
                self.link.send(L.RSP_ACK, bytes([cmd, 0]))
            else:
                self.link.send(L.RSP_ACK, bytes([cmd, 7]))
        elif cmd == L.CMD_SHUTDOWN:
            self.link.send(L.RSP_ACK, bytes([cmd, 0]))
            self._shutdown()

    # ---------------- 任务 ----------------
    def _shoot_task(self, burst, interval):
        if self.mode != MODE_IDLE:
            return
        self.mode = MODE_SHOOTING
        try:
            for i in range(max(1, burst)):
                tag = time.strftime("%Y%m%d_%H%M%S")
                if not self.store.ensure_space(64):
                    self.last_err = 3; break
                ts, shots = self.cam.shoot(tag)
                paths = {}
                for idx, (jpg, dng) in shots.items():
                    jp = os.path.join(self.store.data_dir, f"cam{idx}_{ts}.jpg")
                    open(jp, "wb").write(jpg)
                    paths[idx] = (jp, jpg)
                    if dng:
                        os.rename(dng, os.path.join(self.store.data_dir, dng))
                # 拼接全景
                if 0 in paths and 1 in paths and self.stitcher:
                    i0 = cv2.imdecode(np.frombuffer(paths[0][1], np.uint8), cv2.IMREAD_COLOR)
                    i1 = cv2.imdecode(np.frombuffer(paths[1][1], np.uint8), cv2.IMREAD_COLOR)
                    pano = self.stitcher.stitch(i0, i1)
                    pp = os.path.join(self.store.data_dir, f"pano_{ts}.jpg")
                    cv2.imwrite(pp, pano, [cv2.IMWRITE_JPEG_QUALITY, cfg["jpeg_quality"]])
                    self.store.register(pp, "pano_jpg")
                    # 快视图 (小尺寸, 优先下传)
                    prev = cv2.resize(pano, (cfg["preview_width"], cfg["preview_width"] // 2))
                    pv = os.path.join(self.store.data_dir, f"preview_{ts}.jpg")
                    cv2.imwrite(pv, prev, [cv2.IMWRITE_JPEG_QUALITY, 80])
                    self.store.register(pv, "preview")
                for idx, (jp, _) in paths.items():
                    self.store.register(jp, "cam_jpg")
                if i < burst - 1:
                    time.sleep(interval)
        finally:
            self.mode = MODE_IDLE

    def _start_video(self, dur):
        if self.mode != MODE_IDLE:
            return
        self.mode = MODE_RECORDING
        tag = time.strftime("%Y%m%d_%H%M%S")
        fmt = os.path.join(self.store.data_dir, f"vid_{tag}_cam" + "{idx}.h264")
        self.cam.start_video(fmt, dur)
        self.video_deadline = time.time() + dur
        self._video_fmt = fmt

    def _stop_video(self):
        self.cam.stop_video()
        if hasattr(self, "_video_fmt"):
            for idx in (0, 1):
                p = self._video_fmt.format(idx=idx)
                if os.path.exists(p):
                    self.store.register(p, "video")
        self.mode = MODE_IDLE
        self.video_deadline = None

    def _shutdown(self):
        self._stop = True
        if self.mode == MODE_RECORDING:
            self._stop_video()
        time.sleep(1)
        if ON_TARGET:
            os.system("sync; shutdown -h now")
        sys.exit(0)

    def _status(self):
        t0 = self.cam.temperature(0); t1 = self.cam.temperature(1)
        return struct.pack("<BBBBbBHHHIb6x",
            self.mode, self.cam.ok[0], self.cam.ok[1], 0,
            t0, t1, self.store.free_mb(), 0,
            1 if self.cam.recording else 0,
            len(self.store.index["files"]), int(time.monotonic()-_T0), self.last_err)  # uptime(s), 非纪元

    # ---------------- 主循环 ----------------
    def run(self):
        print("[payload] PANO-3U payload started, ON_TARGET =", ON_TARGET)
        while not self._stop:
            if self.link:
                self.link.poll()
            # 视频到时自动停
            if self.mode == MODE_RECORDING and self.video_deadline \
                    and time.time() > self.video_deadline:
                self._stop_video()
            # 心跳超时: 不自动关机(OBC侧负责断电), 仅记录
            if time.time() - self.last_ping > cfg["heartbeat_timeout_s"] * 6:
                self.last_err = 8
            time.sleep(0.02)


if __name__ == "__main__":
    app = PayloadApp()
    signal.signal(signal.SIGTERM, lambda *a: app._shutdown())
    app.run()
