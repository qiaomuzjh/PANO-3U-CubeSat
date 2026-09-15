# 🚀 GitHub 发布操作指南(张嘉豪专用,三选一)

本机环境:**未安装 git**,本机无你的 GitHub 凭证(QQ 浏览器的登录态无法传给命令行),
所以仓库内容我已 100% 备好在 `桌面\PANO-3U-CubeSat`,你只需按下面三种方式**任选其一**完成发布。

推荐顺序:**方式 A(GitHub Desktop,最简单)> 方式 B(网页直传)> 方式 C(命令行)**

---

## 方式 A:GitHub Desktop(推荐,10 分钟)

1. 下载安装 **GitHub Desktop**:https://desktop.github.com
2. 打开 GitHub Desktop → `File` → `Add local repository` → 选择
   `C:\Users\qiaomu\Desktop\PANO-3U-CubeSat`
   → 会提示"not a repository",点 `Create a Repository`:
   - Name: `PANO-3U-CubeSat`
   - 勾选 "Keep this code private" **不要勾**(要开源)→ `Create Repository`
3. 顶部菜单 `Repository` → `Push` → 首次会弹登录:
   - `Sign in to github.com` → 浏览器授权(你 QQ 浏览器已登录,直接点 Authorize)
   - 若浏览器默认不是 QQ 浏览器:在 GitHub Desktop 设置里 `Options → Advanced`
     选择默认浏览器,或复制授权链接到 QQ 浏览器打开
4. 推送前先去网页建仓库:浏览器打开 https://github.com/new
   - Repository name: `PANO-3U-CubeSat`
   - 选 **Public** → 不要勾任何初始化选项(README/LICENSE 都已备好)→ `Create`
   - 回到 GitHub Desktop → `Repository` → `Push` → `Publish repository`
     (取消勾选 "Keep this code private")→ 完成 ✅

---

## 方式 B:网页直传(零安装,~5 分钟)

1. 浏览器打开 https://github.com/new
   - Name: `PANO-3U-CubeSat`;选 **Public**;**全部取消勾选**(README/LICENSE/gitignore 我已备好)→ `Create repository`
2. 在新仓库页点 **"uploading an existing file"**
3. 把 `桌面\PANO-3U-CubeSat` 里的**全部内容**(不是文件夹本身)拖入上传框
   - ⚠️ 网页上传单文件限 25 MB、总数最多 100 个文件——
     本包 234 个文件超限,建议:先拖 00~10 的文件夹(共 ~200 个),
     `99_归档` 与 `09_软件/源码` 若提示过多,分 2-3 批拖入
4. 底部 Commit message 填 `PANO-3U 全套开源设计制造文件包 v1.0` → `Commit changes` → 完成 ✅
   (更省事还是用方式 A/C)

---

## 方式 C:命令行 git(装 Git 后最通用)

1. 安装 Git for Windows:https://git-scm.com/download/win(一路下一步)
2. **Win+R → `cmd`**,逐条执行(用户名/邮箱换成你的):

```bat
cd /d C:\Users\qiaomu\Desktop\PANO-3U-CubeSat
git init
git add .
git commit -m "PANO-3U 全套开源设计制造文件包 v1.0"
git branch -M main
```

3. **配置代理**(你挂了梯子,git 不走系统代理,必须单独配;端口看你梯子软件,
   Clash 默认 7890,v2rayN 默认 10809):

```bat
git config --global http.proxy  http://127.0.0.1:7890
git config --global https.proxy http://127.0.0.1:7890
git config --global user.name  "Zhang Jiahao"
git config --global user.email "你的GitHub邮箱"
```

4. 浏览器打开 https://github.com/new → Name: `PANO-3U-CubeSat` → Public →
   **取消勾选 README/LICENSE/gitignore** → Create

5. **用 PAT 登录推送**(命令行不能用浏览器登录态,需要令牌):
   - 打开 https://github.com/settings/tokens → `Generate new token (classic)`
   - 勾选 `repo` 权限 → 生成后**立即复制**(只显示一次)
   - 回到 cmd:

```bat
git remote add origin https://github.com/你的用户名/PANO-3U-CubeSat.git
git push -u origin main
```

   - 弹出登录窗口:用户名=你的 GitHub 用户名,密码=粘贴刚才的 **PAT 令牌**
   - 推送完成 ✅ 打开仓库页即可看到全部文件

---

## 📋 发布前最后检查(已替你核过)

- ✅ 无任何密钥/令牌/个人隐私信息(签署栏均为空白占位)
- ✅ 版权与署名:NOTICE/LICENSE 已写"张嘉豪 (Zhang Jiahao)",CC BY-NC 4.0 全文
- ✅ 频率/发射安全内容均为公开标准知识;地面站坐标仅到城市级
- ⚠️ 开源即公开:BOM 里的采购价格、地面站位置(北京)如介意可自行删除后推送
- ⚠️ NC 许可:GitHub 开源无碍;但 **CC BY-NC 不是 OSI 开源许可证**,严格说是
  "免费公开+非商用";若日后希望商用友好,可另加 `LICENSE-CODE`(GPL/MIT)双许可

## 建议仓库设置

- Description: `PANO-3U open-source 3U CubeSat — full design & manufacturing package (GB drawings / STEP / KiCad / docs) CC BY-NC 4.0`
- Topics: `cubesat` `satellite` `open-source-hardware` `space` `panoramic-camera` `step` `kicad`
- 若单文件超 25 MB 报错(不太会,最大 6.5 MB),或日后模型变大,再考虑 Git LFS
