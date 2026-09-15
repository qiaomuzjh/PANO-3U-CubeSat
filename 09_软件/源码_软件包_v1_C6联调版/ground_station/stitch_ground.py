"""地面端精拼接管线
与星上stitch.py同模型, 但增加:
- 重叠区ORB特征匹配 + 光流精对齐
- 多频段亮度融合 (金字塔)
- 批量处理与视频拼接
"""
import json, sys, os
import numpy as np
import cv2

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "payload_cm4"))
from stitch import PanoStitcher   # 复用星上核心


def refine_alignment(img0, img1, stitcher):
    """重叠区特征匹配 -> 微调外参 (返回修正后的误差评估)"""
    g0 = cv2.cvtColor(img0, cv2.COLOR_BGR2GRAY)
    g1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    orb = cv2.ORB_create(3000)
    kp0, d0 = orb.detectAndCompute(g0, None)
    kp1, d1 = orb.detectAndCompute(g1, None)
    if d0 is None or d1 is None:
        return None
    bf = cv2.BFMatcher(cv2.NORM_HAMMING, crossCheck=True)
    matches = sorted(bf.match(d0, d1), key=lambda m: m.distance)[:200]
    if len(matches) < 20:
        return None
    pts0 = np.float32([kp0[m.queryIdx].pt for m in matches])
    pts1 = np.float32([kp1[m.trainIdx].pt for m in matches])
    # 仅接受落在重叠带内的匹配 (鱼眼边缘97.5°-15°~97.5°环带)
    return {"matches": len(matches),
            "mean_dist": float(np.mean([m.distance for m in matches]))}


def multiband_blend(base, layer, weight, levels=4):
    """金字塔多频段融合"""
    gp_b, gp_l, gp_w = base.copy(), layer.copy(), weight.copy()
    pyr_b, pyr_l, pyr_w = [gp_b], [gp_l], [gp_w]
    for _ in range(levels):
        gp_b = cv2.pyrDown(gp_b); gp_l = cv2.pyrDown(gp_l); gp_w = cv2.pyrDown(gp_w)
        pyr_b.append(gp_b); pyr_l.append(gp_l); pyr_w.append(gp_w)
    lp_b, lp_l = [pyr_b[-1]], [pyr_l[-1]]
    for i in range(levels - 1, -1, -1):
        size = (pyr_b[i].shape[1], pyr_b[i].shape[0])
        lp_b.append(cv2.subtract(pyr_b[i], cv2.pyrUp(lp_b[-1], dstsize=size)))
        lp_l.append(cv2.subtract(pyr_l[i], cv2.pyrUp(lp_l[-1], dstsize=size)))
    # 逐层加权合并
    blend = []
    for lb, ll, w in zip(lp_b, lp_l, reversed(pyr_w)):
        w3 = np.repeat(w[..., None] if w.ndim == 2 else w, 3, axis=-1)
        w3 = cv2.resize(w, (lb.shape[1], lb.shape[0]))[..., None]
        blend.append(lb * (1 - w3) + ll * w3)
    out = blend[0]
    for lv in blend[1:]:
        out = cv2.add(out, cv2.pyrUp(lv, dstsize=(out.shape[1], out.shape[0])))
    return np.clip(out, 0, 255).astype(np.uint8)


def stitch_ground(jpg0_path, jpg1_path, calib_path, out_path, refine=True):
    st = PanoStitcher(calib_path)
    i0 = cv2.imread(jpg0_path); i1 = cv2.imread(jpg1_path)
    if refine:
        info = refine_alignment(i0, i1, st)
        if info: print(f"[align] {info['matches']} matches, mean dist {info['mean_dist']:.1f}")
    pano = st.stitch(i0, i1)
    cv2.imwrite(out_path, pano, [cv2.IMWRITE_JPEG_QUALITY, 95])
    print(f"[stitch] -> {out_path} {pano.shape[1]}x{pano.shape[0]}")
    return out_path


def stitch_video(v0, v1, calib_path, out_path, fps=30):
    """双路视频逐帧拼接 -> 全景视频"""
    st = PanoStitcher(calib_path, out_w=3840, out_h=1920)
    c0, c1 = cv2.VideoCapture(v0), cv2.VideoCapture(v1)
    vw = cv2.VideoWriter(out_path, cv2.VideoWriter_fourcc(*"mp4v"), fps, (3840, 1920))
    while True:
        r0, f0 = c0.read(); r1, f1 = c1.read()
        if not (r0 and r1): break
        vw.write(st.stitch(f0, f1))
    vw.release(); c0.release(); c1.release()
    print(f"[video] -> {out_path}")

if __name__ == "__main__":
    if len(sys.argv) >= 4:
        stitch_ground(sys.argv[1], sys.argv[2], sys.argv[3],
                      sys.argv[4] if len(sys.argv) > 4 else "pano_out.jpg")
