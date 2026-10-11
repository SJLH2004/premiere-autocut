# 第三方组件与许可声明

> **为什么许可信息分散在两个文件里**
>
> `LICENSE` 只放**未经改动的 MIT 原文** —— 这样 GitHub、SPDX、各类许可证
> 扫描工具才能正确识别本项目为 MIT。
> 任何附加说明（尤其是依赖的 GPLv3 传染性）都写在本文件里，
> 避免破坏 `LICENSE` 的可识别性。

本文件说明本项目**包含什么、依赖什么、不包含什么**，供使用者与再分发者判断合规性。

---

## 一、本项目自己编写的部分 → MIT

以下全部为本项目原创，采用仓库根目录的 MIT 许可：

| 路径 | 内容 |
|---|---|
| `autocut/` | 配置加载、CEP 安装器、环境自检 |
| `scripts/` | 时间线搭建入口、安装与自检入口 |
| `cep/` | **自研 CEP 桥接扩展**（见下节） |
| `docs/` | 文档 |
| `examples/` | 示例数据 |

其中 `cep/js/cep-bridge.js` 是**干净实现**：它只调用 CEP 运行时公开注入的
`window.__adobe_cep__` 接口（`getSystemPath` / `evalScript` / `getHostEnvironment`），
不含任何 Adobe 源码。

---

## 二、我们**刻意不再分发**的组件

### 1. Adobe CSInterface.js —— 已移除

Adobe 随 CEP SDK 分发的 `CSInterface.js` 是**专有文件**，其文件头声明：

> 该文件的使用、修改与分发须遵循随附的 Adobe 许可协议；
> 若你从 Adobe 之外的来源取得该文件，则其使用、修改或分发
> **需要 Adobe 事先书面许可**。

**处置**：本仓库**不包含**该文件，并在 `.gitignore` 中屏蔽。
原先对它的 3 处调用改由自研的 `cep/js/cep-bridge.js` 提供，
接口名保持一致（`CSInterface` / `SystemPath` / `evalScript`），因此既有代码无需改动。

> 如果你**自己的**项目已经合法持有 CSInterface.js，可以自行放置；
> 但请勿把它提交到公开仓库。

### 2. 官方 pymiere_link.zxp —— 未使用

该官方扩展包在各平台已下不到。本项目因此自研了等价的 CEP 扩展。
我们**不重新分发任何官方扩展包**。

### 3. Adobe Premiere Pro / Media Encoder

本项目**不包含也不分发** Adobe 应用或其任何二进制组件。
使用者需自行取得并遵守 Adobe 的授权条款。

---

## 三、运行时依赖（不打包，由使用者自行安装）

### pymiere —— GPLv3 ⚠️

| 项 | 值 |
|---|---|
| 包名 | `pymiere` |
| 测试版本 | 1.4.1 |
| 许可 | **GNU General Public License v3.0** |
| 上游 | https://github.com/qmasingarbe/pymiere |
| 作者 | Quentin Masingarbe |

**这一点必须看清**：pymiere 是 **GPLv3**，不是宽松许可。对本项目的影响：

- 本项目**自身代码**（不含 pymiere）按 MIT 发布，这一点成立；
- 但 pymiere 的 GPLv3 具有传染性。**如果你把依赖 pymiere 的本项目作为整体再分发**，
  该整体应当遵循 GPLv3，并向接收者提供完整对应源码；
- 因此本仓库**不 vendor（不内嵌）pymiere 的任何源码**，只通过 `requirements.txt` 声明依赖，
  由使用者用 `pip install` 自行获取。

> 这不是法律意见。若用于商业分发，请咨询专业人士。

### 其它依赖

| 包 | 许可 | 用途 |
|---|---|---|
| `openpyxl` | MIT | 读取 `.xlsx` 分镜执行表 |
| `requests` | Apache-2.0 | pymiere 内部使用（间接依赖） |

---

## 四、使用者需要自备的环境

| 组件 | 说明 |
|---|---|
| Premiere Pro | 2023 及以上（本项目在 23.2.0 实测） |
| Python | 3.8+ |
| CEP 调试模式 | 由 `scripts/install_cep.py` 自动写入注册表放行 |

---

## 五、合规自检清单

再分发本项目前，请确认：

- [ ] 仓库内**没有** `CSInterface.js`（`git status` 与 `.gitignore` 均已覆盖）
- [ ] 未提交任何 `.prproj` / 视频素材 / 客户分镜表
- [ ] 未内嵌 pymiere 源码；`requirements.txt` 只声明依赖
- [ ] 若整体分发依赖 pymiere 的作品，已按 GPLv3 提供源码
- [ ] 已保留所有原创文件的 MIT 许可声明

---

## 六、文档中提及的产品名

`Adobe`、`Premiere Pro`、`Media Encoder` 是 Adobe 的商标。
本项目为**独立第三方工具**，与 Adobe 无隶属、赞助或背书关系。
文档中提及这些名称仅用于说明兼容性（合理使用）。