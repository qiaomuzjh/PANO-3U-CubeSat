# PANO-3U KiCad 工程 README(v2 / 投产核对版)

**版本:v2 / 2026-09** | KiCad 7.0+ 打开 `PANO-3U.kicad_pro`
**本版修正(相对 vB README):**
1. ~~TPS2553×4 电子保险丝~~ → **U20 = TPS2557(CM4 支路 3 A),U21-U23 = TPS2553**(原理图 vB 已正确,本 README 旧文案有误,已勘误);
2. 数传默认速率 **57.6 kbps**(链路裕量 10.7 dB;9.6 kbps 为备份速率)——固件 comm.c 默认参数同步修改;
3. 新增 `板框模板/`:四种板的 PCB-000 外形(.kicad_pcb,Edge.Cuts 已绘 90×90 四角 45° 切口 + 4×Ø3.2 安装孔),Layout 直接导入。

## 工程结构
| 文件 | 内容 |
|---|---|
| `PANO-3U.kicad_pro` | 工程文件 |
| `PANO-3U.kicad_sch` | 根图(层次化入口) |
| `eps.kicad_sch` | E8 EPS(U1-U4 LT3652 MPPT、U6 TPS54331、U20 TPS2557、U21-23 TPS2553、INA226×4) |
| `obc.kicad_sch` | E7 OBC(STM32F405、TPS3823、W25Q128、DS3231、MPU-9250、QMC5883L、DRV8837×3) |
| `comm.kicad_sch` | E9 UHF(Si4463、RA07H4452M 1W PA、PE4259、SAW、TCXO 30MHz) |
| `cm4_carrier.kicad_sch` | E2 CM4 载板(DF40C-100DP、双 22P CSI、TPS22965、microSD) |
| `PANO-3U.kicad_sym` | 项目符号库(18 个自定义符号) |
| `板框模板/` | PCB-000 外形模板 ×4(本版新增) |

## 投板前核对清单(必须逐条签署)
1. **自定义符号引脚映射**(18 个符号,引脚号为逻辑编号):
   - LT3652 → MSOP-12EP 实际封装(占位 DFN16 必须改);
   - STM32F405RGT6 → LQFP-64 实际引脚号;
   - RA07H4452M / PE4259 / Si4463 模块逐脚核对;
2. R/C/L/D/连接器使用 KiCad 官方库,天然正确;
3. 运行 **ERC** 全绿后再 Layout;
4. 电源完整性:5V 走线 ≥0.5 mm(或敷铜),VBAT ≥0.8 mm;MIPI 差分 100Ω 等长 ±0.5 mm;
5. **U20 必须 TPS2557**:BOM/位号/丝印三处核对,防止与 TPS2553 混贴(两者封印相似);
6. CM4 双相机:CAM1 为 2-lane,相机 2 的 D2/D3 已断开;4K30 带宽实测不足则切换 CM5/USB3 备选;
7. 板框以 `板框模板/*.kicad_pcb`(PCB-000,与生产图纸册 P15 一致)为准;
8. 网表与 `BOM v2.xlsx`(E 系列)、`ELE-002 规格书` 三处一致后方可投板。

## 与其他文件的协调
原理图网络名/位号 ↔ BOM v2(E 系列)↔ ELE-002 规格书 逐条对应;改动任何一处四处同步
(另两处:生产图纸册 ELE-403 器件布局、固件信号命名)。
