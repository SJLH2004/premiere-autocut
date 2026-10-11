# 故障排查

按现象查。每一条都先给**最可能的原因**，再给处理办法。

---

## 连接类

### 所有 `evalScript` 返回 `EvalScript error.`

**原因**：ExtendScript 引擎没起来。

**处理**
1. 检查 `cep/CSXS/manifest.xml` 里的 `<ScriptPath>` 是否指向**存在的 .jsx 文件**
   （必须写文件路径，不是目录 —— 见 pitfalls 坑 8）
2. 确认 `cep/jsx/` 下有 `com.pymiere.link.jsx` 与 `ExtendJSON.jsx`

### 连 `"alive";` 都超时 20–25 秒

**原因（最常见）**：**PR 主线程被模态框卡住**。

**处理**
看一眼 Premiere 窗口，有没有弹框。点掉即恢复。
常见触发源：`changeMediaPath`、`createNewSequence` 传错参数。

### `No connection` / `ConnectionError`

**处理**
1. 面板是否已加载：菜单 **窗口 → 扩展 → Pymiere Link**，应显示「已就绪」
2. 3000 端口是否被占用：`netstat -ano | findstr :3000`
3. **代理问题**：跑 `python scripts/probe.py`，看「代理设置」那一项

### `TypeError: ... argument after ** must be a mapping, not str`

**原因**：`$._pymiere` 缺失 —— 见 **pitfalls 坑 1**。

---

## 安装类

### 扩展装好了但菜单里看不到

1. 确认注册表已写入（`scripts/install_cep.py` 会自动做）：
   `HKCU\\Software\\Adobe\\CSXS.8` ~ `CSXS.12` 下的 `PlayerDebugMode = "1"`
2. **重启 Premiere**（不是重载，是完整重启）
3. 确认目录正确：
   `C:\\Program Files\\Common Files\\Adobe\\CEP\\extensions\\com.pymiere.link\\`

### 改了扩展代码但没生效

面板里**取消勾选再重新勾选**「Pymiere Link」即可重载。
如果换了目录，必须重启 PR。

### `reg.exe` 被安全软件拦截

`install_cep.py` 已改用 Python 的 `winreg`，绕开 `reg.exe`。
若仍失败，会打印具体错误，可手动设置。

---

## 时间线类

### 片段数多于镜头数 / 内容错位

**原因**：用了 `insertClip` 而不是 `overwriteClip` —— 见 **pitfalls 坑 10**。

### 序列被撑得特别长 / 音频轨一堆杂音

**原因**：`mediaType` 只处理了视频没处理音频 —— 见 **pitfalls 坑 11**。

### 序列建了但脚本报「创建序列失败」

**原因**：弹框超时导致返回 `None`，但序列**实际已经建好**。

**处理**：脚本会自动再查找一次。确认面板可复用即可，不用重建。

### `--wipe` 之后仍有旧音频

**原因**：`--wipe` 只清 V1 是不够的。

**处理**：本项目已清所有视频轨 **和** 音频轨。如仍有残留，手动在 PR 里删除音频轨片段。

---

## 素材类

### 提示「缺代理」

脚本默认按 `{素材名}_Proxy.mp4` 找代理。
如果你的代理命名不同，改 `config.json` 的 `proxy_suffix`。

### 素材目录不可访问

检查 `config.json` 的 `media_dir`：
- 用**正斜杠**或**双反斜杠**（JSON 里单反斜杠是转义符）
- 路径不要带结尾斜杠

### 导入后 PR 卡住两分钟

正常。PR 在生成峰值文件、做音频一致性分析。大素材（几百 MB）尤其明显。
面板里把超时上限设为 300 秒就是为这个场景（见 `cep/index.html`）。

---

## 还是不行？

跑 `python scripts/probe.py`，把输出贴到 issue 里。
它会逐项检查：Python / pymiere / 面板端口 / 代理 / PR 进程 / ExtendScript 链路。
