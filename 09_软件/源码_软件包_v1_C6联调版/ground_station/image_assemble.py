"""图像文件重组: 收块、位图跟踪、缺失重传请求、落盘"""
import os, zlib, struct, json, time

CHUNK = 200

class FileAssembler:
    def __init__(self, out_dir="received"):
        self.out_dir = out_dir
        os.makedirs(out_dir, exist_ok=True)
        self.pending = {}   # file_id -> {total, chunks:{no:data}, bitmap}
        self.state_path = os.path.join(out_dir, "_assembly.json")
        self._restore()

    def _restore(self):
        """断电恢复: 已收块存盘, 重启续收"""
        if os.path.exists(self.state_path):
            st = json.load(open(self.state_path))
            for fid, info in st.items():
                d = os.path.join(self.out_dir, f"fid{fid}")
                if os.path.isdir(d):
                    chunks = {}
                    for fn in os.listdir(d):
                        if fn.startswith("c"):
                            chunks[int(fn[1:])] = open(os.path.join(d, fn), "rb").read()
                    self.pending[int(fid)] = {"total": info["total"], "chunks": chunks}

    def _persist(self, fid):
        d = os.path.join(self.out_dir, f"fid{fid}")
        os.makedirs(d, exist_ok=True)
        p = self.pending[fid]
        for no, data in p["chunks"].items():
            fp = os.path.join(d, f"c{no}")
            if not os.path.exists(fp):
                open(fp, "wb").write(data)
        st = {}
        if os.path.exists(self.state_path):
            st = json.load(open(self.state_path))
        st[str(fid)] = {"total": p["total"]}
        json.dump(st, open(self.state_path, "w"))

    def feed(self, pkt):
        """喂入一个chunk包; 返回完成文件路径或None"""
        fid, no = pkt["file_id"], pkt["chunk_no"]
        p = self.pending.setdefault(fid, {"total": pkt["total"], "chunks": {}})
        p["total"] = pkt["total"]
        if no not in p["chunks"]:
            p["chunks"][no] = pkt["data"]
        if len(p["chunks"]) % 500 == 0:
            self._persist(fid)
        if len(p["chunks"]) == p["total"]:
            return self._finish(fid)
        return None

    def _finish(self, fid):
        p = self.pending.pop(fid)
        blob = b"".join(p["chunks"][i] for i in range(p["total"]))
        path = os.path.join(self.out_dir, f"file_{fid}.bin")
        open(path, "wb").write(blob)
        d = os.path.join(self.out_dir, f"fid{fid}")
        for fn in os.listdir(d): os.remove(os.path.join(d, fn))
        os.rmdir(d)
        st = json.load(open(self.state_path)) if os.path.exists(self.state_path) else {}
        st.pop(str(fid), None)
        json.dump(st, open(self.state_path, "w"))
        return path

    def missing_list(self, fid):
        """生成缺失块清单 -> 上行REQ_MISSING载荷"""
        p = self.pending.get(fid)
        if not p: return None
        missing = [i for i in range(p["total"]) if i not in p["chunks"]]
        body = struct.pack("<IHH", fid, len(missing), 0)
        body += b"".join(struct.pack("<H", m) for m in missing[:120])  # 单帧上限
        return body

    def progress(self):
        return {fid: f"{len(p['chunks'])}/{p['total']}"
                for fid, p in self.pending.items()}
