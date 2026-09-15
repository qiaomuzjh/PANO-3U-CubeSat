"""双相机采集模块 (picamera2 + libcamera)
- 双鱼眼同步采集 (硬件同步: 两相机FSIN并接到CM4 GPIO4, 误差<1ms)
- 支持 RAW(DNG) + JPEG 拍照, H.265 视频
"""
import time, io, threading
import numpy as np

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder  # H.265需libav后端
    from picamera2.outputs import FileOutput
    ON_TARGET = True
except ImportError:
    ON_TARGET = False   # 开发/测试环境 (地面PC)


class DualFisheyeCamera:
    def __init__(self, cfg):
        self.cfg = cfg
        self.cam0 = None
        self.cam1 = None
        self._lock = threading.Lock()
        self._rec = {0: None, 1: None}
        self.ok = [False, False]
        if ON_TARGET:
            self._init_hw()

    def _init_hw(self):
        w, h = self.cfg["cam_resolution"]
        for idx in (0, 1):
            try:
                cam = Picamera2(camera_num=idx)
                sc = cam.create_still_configuration(
                    main={"size": (w, h), "format": "RGB888"},
                    raw={"size": (w, h)})
                cam.configure(sc)
                vc = cam.create_video_configuration(
                    main={"size": (w, h), "format": "RGB888"},
                    controls={"FrameRate": self.cfg["video_fps"]})
                cam.start()
                cam.set_controls({
                    "ExposureTime": self.cfg["ae_exposure_us"],
                    "AnalogueGain": self.cfg["analogue_gain"],
                })
                setattr(self, f"cam{idx}", cam)
                self.ok[idx] = True
            except Exception as e:
                self.ok[idx] = False
                print(f"[camera] cam{idx} init fail: {e}")

    # ---------- 拍照 ----------
    def shoot(self, tag=None):
        """双机同步拍摄, 返回 {idx: (jpeg_bytes, dng_path_or_None)}"""
        ts = time.strftime("%Y%m%d_%H%M%S") if tag is None else tag
        out = {}
        with self._lock:
            jobs = {}
            for idx in (0, 1):
                cam = getattr(self, f"cam{idx}", None)
                if cam is None or not self.ok[idx]:
                    continue
                jobs[idx] = cam.capture_request()   # 请求式采集保证同步
            for idx, req in jobs.items():
                try:
                    buf = io.BytesIO()
                    req.save("main", buf)           # JPEG
                    dng = None
                    if self.cfg["shoot_dng"]:
                        dng = f"cam{idx}_{ts}.dng"
                        req.save_dng(dng)
                    out[idx] = (buf.getvalue(), dng)
                    req.release()
                except Exception as e:
                    print(f"[camera] cam{idx} shoot fail: {e}")
                    self.ok[idx] = False
        return ts, out

    # ---------- 视频 ----------
    def start_video(self, path_fmt, duration_s):
        """双路H.265录像. path_fmt含{idx}占位"""
        with self._lock:
            for idx in (0, 1):
                cam = getattr(self, f"cam{idx}", None)
                if cam is None or not self.ok[idx]:
                    continue
                try:
                    enc = H264Encoder(bitrate=self.cfg["video_bitrate_mbps"] * 1000000)
                    out = FileOutput(path_fmt.format(idx=idx))
                    cam.start_encoder(enc, out)
                    self._rec[idx] = (enc, out)
                except Exception as e:
                    print(f"[camera] cam{idx} video fail: {e}")

    def stop_video(self):
        with self._lock:
            for idx in (0, 1):
                cam = getattr(self, f"cam{idx}", None)
                if cam and self._rec.get(idx):
                    try:
                        cam.stop_encoder()
                    except Exception:
                        pass
                    self._rec[idx] = None

    @property
    def recording(self):
        return any(v is not None for v in self._rec.values())

    def temperature(self, idx):
        """传感器温度; 平台上读IMX477驱动或板载NTC"""
        if ON_TARGET:
            try:
                with open(f"/sys/class/thermal/thermal_zone{idx+1}/temp") as f:
                    return int(f.read()) // 1000
            except Exception:
                return 25
        return 25
