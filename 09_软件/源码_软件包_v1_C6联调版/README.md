# PANO-3U 软件包

版本 B / 2026-09 — 双鱼眼全景立方星完整软件系统

## 组成

```
软件包/
├── docs/通信协议规范.md        板间链路 + UHF上下行 帧格式/指令/错误码
├── payload_cm4/               ★ 星上载荷软件 (CM4, Python3, Raspberry Pi OS)
│   ├── main.py                主程序/状态机/systemd服务入口
│   ├── camera.py              双鱼眼同步采集 (picamera2, RAW+H.265)
│   ├── stitch.py              全景拼接核心 (等距投影+重叠区加权融合)
│   ├── storage.py             文件登记/分块/断电保护/空间回收
│   ├── link.py                OBC链路 (HDLC帧+CRC16, 流式解码)
│   ├── config.py              参数表 (可在轨更新)
│   └── tests/                 6项单元测试 (全部通过)
├── obc_firmware/              ★ OBC飞控固件 (STM32F405, C/HAL/FreeRTOS)
│   └── Core/{Src,Inc}/        main/fsm/adcs/comm/payload_mgr/驱动/日志
└── ground_station/            ★ 地面站 (Python3)
    ├── ground_station.py      主控 (对接Direwolf KISS)
    ├── receiver.py            AX.25解析 + 下行包解码
    ├── image_assemble.py      图像分块重组/断点续传/断电恢复
    ├── stitch_ground.py       地面精拼接 (特征匹配+多频段融合)
    ├── calibrate.py           出厂标定工具 (旋转棋盘格法)
    └── pass_predict.py        过境预测 (TLE+SGP4)
```

## 部署

**CM4 星上**：
```bash
sudo cp -r payload_cm4 /opt/pano3u/
sudo systemctl enable /opt/pano3u/pano3u-payload.service
# calibration.json 由出厂标定生成后放入 /opt/pano3u/
```

**OBC**：见 `obc_firmware/README.md`（CubeMX/PlatformIO 构建）。

**地面站**（Linux + RTL-SDR 或 UHF 电台声卡）：
```bash
pip install opencv-python numpy skyfield pyserial
direwolf -t 0 -r 48000 -   # 或接电台声卡
python3 ground_station/ground_station.py --kiss 127.0.0.1:8001
```

## 研制测试顺序

1. `pytest payload_cm4/tests/` —— 协议/存储/拼接单元测试（PC 上跑）
2. 桌面联调：CM4 实物 + USB-串口 ↔ 跑通 OBC 协议的 PC 模拟器
3. 双相机标定：`calibrate.py` 生成 `calibration.json`
4. 星地链路拉距：SDR 发信标 → 地面站解码验证
5. 整星联试：振动/热真空后复测拍摄与下传

## 关键性能

- 拍照→全景图生成：约 8 s（5760×2880，含双 RAW 采集）
- 视频：双路 4K30 H.265，码率 25 Mbps/路
- 下行：单过境 ≈400 KB（9.6 kbps×8 min×70% 效率），5 MB 全景图约 12 个过境
- 断点续传：块级位图 + 选择重传，支持跨过境断点
