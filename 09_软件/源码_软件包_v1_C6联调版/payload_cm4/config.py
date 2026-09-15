"""PANO-3U 载荷配置 (CM4)
所有可调参数集中于此; 星上参数表 param_table.json 可覆盖默认值
"""
import json, os

DEFAULTS = {
    # 相机
    "cam_resolution": [4056, 3040],
    "cam0_name": "cam0",          # +Z 相机 (CSI0, 4-lane)
    "cam1_name": "cam1",          # -Z 相机 (CSI1, 2-lane)
    "ae_exposure_us": 2000,       # 默认曝光 (冻结≤2°/s自旋)
    "analogue_gain": 2.0,
    "awb_mode": "auto",
    # 视频
    "video_fps": 30,
    "video_bitrate_mbps": 25,     # 每路 H.265
    "video_max_duration_s": 900,
    # 拍照
    "shoot_dng": True,            # 存RAW(DNG)+JPEG
    "jpeg_quality": 92,
    # 拼接 (星上快视)
    "pano_width": 5760,
    "pano_height": 2880,
    "preview_width": 1024,        # 快视下传分辨率
    "calib_file": "calibration.json",
    # 存储
    "data_dir": "/mnt/sdcard",
    "disk_reserve_mb": 2048,      # 保留空间
    # 链路
    "uart_port": "/dev/ttyAMA1",
    "uart_baud": 115200,
    "heartbeat_timeout_s": 10,    # 超时未收到PING → 等待关机指令
    # 温控
    "temp_min_c": -10,
    "temp_max_c": 55,
}

class Config:
    def __init__(self, path="/opt/pano3u/param_table.json"):
        self.cfg = dict(DEFAULTS)
        if os.path.exists(path):
            try:
                self.cfg.update(json.load(open(path)))
            except Exception:
                pass  # 参数表损坏时用默认值, 不致命
        self.path = path
    def __getitem__(self, k): return self.cfg[k]
    def set(self, k, v):
        self.cfg[k] = v
        try:
            json.dump(self.cfg, open(self.path, "w"))
        except Exception:
            pass

cfg = Config()
