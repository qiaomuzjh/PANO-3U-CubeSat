"""双鱼眼标定工具 (出厂/实验室用)

方法: 旋转棋盘格法 —— 相机固定, 棋盘格在鱼眼全视场内旋转≥30姿态
解算: OpenCV fisheye 模型 (与等距投影+多项式等价描述), 输出 calibration.json

用法: python3 calibrate.py --images calib_shots/cam0/*.jpg --cam cam0 --out calibration.json
"""
import argparse, glob, json
import numpy as np
import cv2

BOARD = (9, 6)          # 棋盘格内角点
SQUARE_M = 0.025        # 格边长25mm

def collect_points(images):
    objp = np.zeros((BOARD[0]*BOARD[1], 3), np.float32)
    objp[:, :2] = np.mgrid[0:BOARD[0], 0:BOARD[1]].T.reshape(-1, 2) * SQUARE_M
    objps, imgps, shape = [], [], None
    for f in images:
        img = cv2.imread(f, cv2.IMREAD_GRAYSCALE)
        if img is None: continue
        shape = img.shape[::-1]
        ok, corners = cv2.findChessboardCornersSB(img, BOARD)
        if ok:
            objps.append(objp); imgps.append(corners)
    return objps, imgps, shape

def calibrate(images, out_w_h):
    objps, imgps, shape = collect_points(images)
    if len(objps) < 15:
        raise RuntimeError(f"有效标定帧不足: {len(objps)}<15, 重拍")
    K = np.zeros((3, 3)); D = np.zeros((4, 1))
    rms, K, D, _, _ = cv2.fisheye.calibrate(
        objps, imgps, shape, K, D, None, None,
        cv2.fisheye.CALIB_RECOMPUTE_EXTRINSIC + cv2.fisheye.CALIB_FIX_SKEW)
    print(f"[calib] RMS = {rms:.3f} px (要求<0.5)")
    # 转为等距投影参数: f取K[0,0], 主点cx,cy; 畸变用k1-k4近似
    return {"f": float(K[0,0]), "cx": float(K[0,2]), "cy": float(K[1,2]),
            "k1": float(D[0,0]), "k2": float(D[1,0]),
            "k3": float(D[2,0]), "k4": float(D[3,0]),
            "R": [1,0,0, 0,1,0, 0,0,1]}   # 外参由双机联合标定覆盖

def stereo_extrinsic(calib0, calib1):
    """双机对置: 光轴反向, 绕Z轴roll由旋转标定确定
       简化: 两相机R相差180°绕Y (背对背), 精值由恒星在轨标定修正"""
    calib1["R"] = [-1,0,0, 0,1,0, 0,0,-1]   # Ry(180°)
    return calib0, calib1

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True)
    ap.add_argument("--cam", required=True, choices=["cam0", "cam1"])
    ap.add_argument("--out", default="calibration.json")
    ap.add_argument("--stereo", action="store_true", help="合并双机并写外参")
    a = ap.parse_args()

    cal = calibrate(sorted(glob.glob(a.images)), None)
    if a.stereo and a.cam == "cam1":
        c = json.load(open(a.out)) if __import__("os").path.exists(a.out) else {}
        c["cam1"] = cal
        c["cam0"], c["cam1"] = stereo_extrinsic(c.get("cam0", {}), cal)
        c.setdefault("pano", {"w": 5760, "h": 2880})
    else:
        c = json.load(open(a.out)) if __import__("os").path.exists(a.out) else {}
        c[a.cam] = cal
        c.setdefault("pano", {"w": 5760, "h": 2880})
    json.dump(c, open(a.out, "w"), indent=2)
    print(f"[calib] -> {a.out}")
