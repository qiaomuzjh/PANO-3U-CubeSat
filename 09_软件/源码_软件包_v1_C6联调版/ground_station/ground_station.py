"""地面站主控: 接收 -> 解码 -> 重组 -> 拼接 -> 显示
运行: python3 ground_station.py [--kiss 127.0.0.1:8001] [--out received/]
"""
import argparse, os, sys, time
sys.path.insert(0, os.path.dirname(__file__))
from receiver import KissReceiver, parse_downlink
from image_assemble import FileAssembler

BEACON_LOG = "beacons.log"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--kiss", default="127.0.0.1:8001")
    ap.add_argument("--out", default="received")
    ap.add_argument("--replay", help="离线回放: 从raw帧文件读(测试用)")
    a = ap.parse_args()

    asm = FileAssembler(a.out)
    done_files = []

    def on_pkt(pkt):
        d = parse_downlink(pkt["payload"])
        if not d: return
        if d["type"] == "beacon":
            line = (f"{time.strftime('%H:%M:%S')} BEACON seq={d['seq']} "
                    f"mode={d['mode']} vbat={d['vbat_mv']}mV i={d['ibat_ma']}mA "
                    f"temp={d['temp']} gyro={d['gyro_dps']} "
                    f"pl_mode={d['pl_mode']} free={d['free_mb']}MB files={d['files']}")
            print(line)
            open(BEACON_LOG, "a").write(line + "\n")
        elif d["type"] == "chunk":
            done = asm.feed(d)
            if done:
                print(f"[完成] file_id={d['file_id']} -> {done}")
                done_files.append(done)
        prog = asm.progress()
        if prog and d["type"] == "chunk" and d["chunk_no"] % 200 == 0:
            print("[进度]", prog)

    if a.replay:
        for line in open(a.replay, "rb").read().split(b"\xc0"):
            if line:
                on_pkt({"payload": line[17:-2] if len(line) > 19 else line})
        return

    host, port = a.kiss.split(":")
    print(f"[地面站] 连接 Direwolf KISS {host}:{port} ...")
    rx = KissReceiver(host, int(port))
    rx.on_packet(on_pkt)
    print("[地面站] 等待信标... (Ctrl-C退出)")
    try:
        rx.run()
    except KeyboardInterrupt:
        print("\n[地面站] 退出. 已收文件:", done_files)

if __name__ == "__main__":
    main()
