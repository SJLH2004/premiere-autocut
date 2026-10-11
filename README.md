# premiere-autocut

**用 Python 实时驱动 Premiere Pro 搭时间线** —— 把分镜执行表变成真实工程。

给一批素材与一张分镜表，脚本会：导入素材 → 挂代理 → 建序列 → 按时间码铺镜头
（含源内入出点）→ 保存工程 → 可选导出。

> 实测环境：**Premiere Pro 2023 (23.2.0) + Windows**，完整搭出过 56 镜双序列工程。
> 脚本只负责把**结构**搭对；节奏、转场、调色、字幕仍由剪辑师决定。

---

## 为什么会有这个项目

官方 `pymiere_link.zxp`（pymiere 所需的 CEP 扩展）在 GitHub 与所有镜像**都已下不到**。
没有它，pymiere 的 Python 端连不上 Premiere。

所以本项目**自研了一个等价的 CEP 桥接扩展**，并把它连同踩坑记录一起开源。
你在 `docs/` 下看到的两篇文档，是让这个项目能真正跑起来的关键：

| 文档 | 内容 |
|---|---|
| **[docs/pitfalls.md](docs/pitfalls.md)** | **11 个实测踩坑** —— CEP 报错信息与真实原因完全不匹配，看这个比查官方文档快 |
| [docs/unsupported-apis.md](docs/unsupported-apis.md) | PR 2023 上**已证实不可用**的 API 与替代方案 |
| [docs/troubleshooting.md](docs/troubleshooting.md) | 按现象排查 |

---

## 架构

```
Python (pymiere)
   │  HTTP POST  http://127.0.0.1:3000
   ▼
自研 CEP 面板 (cep/)
   │  文件轮询中继  C:/prlink/{id}.req → .res
   ▼
cs.evalScript ──> ExtendScript 引擎 ──> Premiere Pro
```

**两个设计要点**（都是被坑出来的，详见 docs/pitfalls.md 坑 2、坑 7）：

1. Python 侧必须绕过本机 HTTP 代理，否则连 `127.0.0.1` 也走代理 → 稳定超时
2. HTTP 回调里不能直接调 `evalScript`（Node 与 CEF 主线程不互通），
   必须用文件轮询把执行动作交回浏览器主线程

---

## 安装

### 1. 依赖

```bash
pip install -r requirements.txt
```

> ⚠️ `pymiere` 是 **GPLv3**。本项目自身代码为 MIT，但整体分发依赖 pymiere 的作品时须遵循 GPLv3。
> 详见 [THIRD-PARTY.md](THIRD-PARTY.md)。

### 2. 安装 CEP 扩展

```bash
python scripts/install_cep.py
```

它会复制扩展到 CEP 目录，并写入注册表放行调试模式（`CSXS.8`~`CSXS.12`）。
然后**重启 Premiere**，菜单 **窗口 → 扩展 → Pymiere Link**，面板应显示「已就绪」。

### 3. 自检

```bash
python scripts/probe.py
```

逐项检查 Python / pymiere / 面板端口 / 代理 / PR 进程 / ExtendScript 链路。
**跑不通时先跑这个**，它会告诉你是哪一环断了。

### 4. 配置

```bash
cp config.example.json config.json
```

`config.json` 说明（该文件已在 `.gitignore` 中，不会被提交）：

| 字段 | 说明 |
|---|---|
| `project_name` | 项目名，用于输出文件命名 |
| `media_dir` | 素材目录（用正斜杠） |
| `shotlist` | 分镜执行表 `.xlsx`（相对 config.json 或绝对路径） |
| `export_dir` | 导出目录 |
| `preset_guid` | 序列预设 GUID，默认 DSLR 1080p25 |
| `proxy_suffix` | 代理文件后缀，默认 `_Proxy` |
| `sequences` | 序列定义：`sheet`（表名）/ `title`（中文名）/ `ascii_name`（建序列用） |
| `columns` | 分镜表列映射，**0-based**；`header_rows` 指定表头占几行 |

---

## 用法

```bash
python scripts/pr_build_timeline.py --help
python scripts/pr_build_timeline.py                 # 只搭时间线
python scripts/pr_build_timeline.py --wipe          # 先清空所有轨道再铺
python scripts/pr_build_timeline.py --limit 5       # 每序列只铺 5 镜（调试）
python scripts/pr_build_timeline.py --export        # 搭完自动导出
```

| 参数 | 说明 |
|---|---|
| `--source proxy\|original` | 用代理铺（快，默认）还是直接导入原片（慢） |
| `--wipe` | 铺之前清空**所有视频轨和音频轨** |
| `--limit N` | 每序列只铺前 N 镜（调试） |
| `--batch N` | 每批导入多少条素材（默认 8，太大 PR 会卡） |
| `--suffix X` | 序列名加后缀（调试用，避免重名） |
| `--no-stack` | 入出点未知的镜头只铺一段（默认分层堆 3 个候选） |
| `--export` | 搭完直接导出 |

### 入出点未知的镜头怎么处理

不赌一段。在素材上取 3 个候选起点（开头 / 中段 / 靠尾），
分别堆到 **V1/V2/V3 + A1/A2/A3**，由剪辑师肉眼挑一段、删掉其余两层。
素材余量不足 2 秒时自动只铺 1 段（堆三层没意义）。

---

## 交付前自检

- [ ] 时间线片段数 == 镜头数（没有多出一堆长尾）
- [ ] 音频轨最远端 ≤ 视频轨最远端（音频没被撑长）
- [ ] 每个片段的源内入出点与分镜表对得上
- [ ] 用的确实是代理（片段名带代理后缀）而不是几百 MB 的原片
- [ ] 项目已 `save()`

---

## 已知边界

- 代理替换：`attachProxy` / `changeMediaPath` 在 PR 2023 不可用，
  本项目改为「直接导入代理 + 生成对照表」，导出前需重链接（见 docs/unsupported-apis.md）
- DJI 代理为 29.97fps、序列 25fps，建议手动「修改 → 解释素材」统一
- 部分 DJI 代理本身无音轨，A 轨片段数少于 V 轨属正常
- 仅在 Windows + PR 2023 实测；macOS 未验证（CEP 路径已适配）

---

## 许可

- 本项目**自身代码**：[MIT](LICENSE)
- 运行时依赖 `pymiere`：**GPLv3** ⚠️
- **不分发任何 Adobe 专有文件**（原 `CSInterface.js` 已用自写的 `cep-bridge.js` 替代）

完整说明见 **[THIRD-PARTY.md](THIRD-PARTY.md)** —— 再分发前请读一遍。

`Adobe`、`Premiere Pro` 是 Adobe 的商标。本项目为独立第三方工具，与 Adobe 无隶属关系。
