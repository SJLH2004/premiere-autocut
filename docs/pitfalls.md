# 实测踩坑记录（11 条）

这些坑全部在 **Premiere Pro 2023 (23.2.0) + Windows** 上实际遇到并解决，
不是从文档推测的。每一条都注明了**症状**，便于你按现象检索。

---

## 坑 1 · pymiere 的对象桥 `$._pymiere` 必须自己实现

**症状**
```
TypeError: Application() argument after ** must be a mapping, not str
```

**原因**
pymiere 的 Python 端通过 HTTP 把 ExtendScript 表达式发给 CEP 面板执行。
它的对象包装依赖全局 `$._pymiere`（存放宿主对象引用与 `generateId()`）。
这个对象由官方 `pymiere_link.zxp` 提供 —— 而该扩展包在 GitHub 与所有镜像都已下不到。

**处理**
在 `cep/jsx/ExtendJSON.jsx` 里自行实现 `$._pymiere`。
缺失时，所有对象包装调用都会失败，且报错信息完全指不到真正原因。

---

## 坑 2 · 本机代理会把 `127.0.0.1` 也代理掉

**症状**
连接 CEP 面板稳定超时，无任何错误堆栈。

**原因**
本机设置了 `HTTP_PROXY`（例如 `127.0.0.1:11426`）。
pymiere 内部用 `requests` 访问 `http://127.0.0.1:3000`，
requests 会读取环境变量里的代理设置，于是连本地回环也走代理 → 必然超时。

**处理**
```python
import os
os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"
import pymiere          # 必须在设置之后再 import
```

**注意顺序**：`import pymiere` 之前必须设好。
本项目的 `autocut.config.prepare_environment()` 自动完成这一步。

> 这是最难定位的坑之一 —— 报错看起来像「面板没开」，
> 但在别的机器上一切正常，很容易怀疑代码。

---

## 坑 3 · `$.global !== $`

**症状**
在 `$.global.X` 上挂的东西能用裸标识符访问，但 pymiere 找不到。

**原因**
实测 `$.global` 与 `$` **不是同一个对象**。
pymiere 查找的是 `$._pymiere`，必须挂在 `$` 本身。

**处理**
两边都挂一份最稳。

---

## 坑 4 · ES3 没有 `Array.prototype.indexOf`

**症状**
```
seen.indexOf is not a function
```

**原因**
ExtendScript 基于 ES3。pymiere 生成的代码里用了 `indexOf`，
连它的 `__del__` 也会调用 `generatedIds.indexOf`。

**处理**
需要 ES5 垫片：`indexOf` / `lastIndexOf` / `forEach` / `map` / `filter` / `String.trim`。
本项目全部放在 `cep/jsx/ExtendJSON.jsx`。

---

## 坑 5 · ExtendScript 里普通 `{}` 也有 `.reflect`

**症状**
字面量对象的 `objectType` 被误判成 `"Object"`。

**原因**
pymiere 用 `isHostObject()` 判断一个值是不是宿主对象，
依据是它有没有 `.reflect`。但 ExtendScript 里普通对象字面量**也有** `.reflect`。

**处理**
必须额外排除 `reflect.name === 'Object'` 的情况。

---

## 坑 6 · `evalScript` 有长度上限，超了**静默失败**

**症状**
较长的脚本不返回结果，也**不报错**，回调根本不来。

**原因**
CEP 的 `evalScript` 走 URL scheme 传参，长度上限约 **4KB**。

**处理**
超过阈值时改为：把代码写入 `.jsx` 文件，再执行 `$.evalFile("路径")`。
本项目在面板里以 1200 字符为阈值切换。

---

## 坑 7 · 在 Node 的 HTTP 回调里调 `evalScript` 不回调

**症状**
HTTP 请求进来后执行脚本，回调永远不触发，请求挂死。

**原因**
CEP 面板同时有 Node 上下文和 CEF 浏览器上下文。
Node 的事件循环与浏览器主线程不互通，
在 Node 回调里直接调 `evalScript` 得不到回调。

**处理：文件轮询中继**
```
Node 侧   ：收到 HTTP 请求 -> 写 C:/prlink/{id}.req
浏览器侧  ：setInterval(pump, 20) 轮询 -> 执行 evalScript -> 写 {id}.res
Node 侧   ：轮询等 {id}.res 出现 -> 作为 HTTP 响应返回
```
执行动作**必须交给浏览器主线程**。

---

## 坑 8 · `<ScriptPath>` 要写**完整文件路径**，不是目录

**症状**
```
Failed to evaluate script file for scripting engine ...
```
所有 `evalScript` 全部失败。

**原因**
`manifest.xml` 里写 `./jsx/`（目录）会让 PlugPlug 建不起 ExtendScript 引擎。

**处理**
写完整文件路径：`./jsx/com.pymiere.link.jsx`

---

## 坑 9 · `createNewSequence` 第二参数要 **GUID**，且中文序列名会卡死主线程

**症状**
调用后 PR 卡住，弹出「新建序列」对话框，脚本超时。

**原因（两个）**
1. 第二参数需要的是**预设 GUID**，不是 `.sqpreset` 文件路径 —— 传路径 PR 不认，直接弹框。
2. 序列名用中文也会触发弹框。

**处理**
- 预设 GUID 从 `.sqpreset` 文件里的 `SequencePreset ClassID` 取。
  本项目默认 DSLR 1080p25：`5e73dd7e-4f86-4917-80eb-08ddb2f4a5f3`
- **先用 ASCII 名建序列**（如 `SEQ_A`），建完再改 `projectItem.name` 为中文 —— **改名不弹框**
- 查找序列时用前缀匹配，这样能认回改名后的序列，避免重复创建

---

## 坑 10 · 必须用 `overwriteClip`，**不能用 `insertClip`**

**症状**
铺完时间线发现片段数远多于镜头数，内容互相错位。

**原因**
`insertClip` 的语义是「插入并后移」，会把已铺内容往后推，
并且把每条素材切开。**实测 27 个镜头铺出了 51 个片段**
（27 个正常 + 24 个被切开的长尾），时间线完全错误。

**处理**
用 `Track.overwriteClip(projectItem, time)` —— 它才是覆盖语义。

---

## 坑 11 · `mediaType` 是 **1=视频、2=音频**，两者互相独立

**症状**
序列被撑到 5 分钟；音频轨上一堆不该有的声音。

**原因**
`setInPoint(x, 4)` 管不住音频（4 是别的类型）。
视频与音频的入出点**各自独立**，只设一边就等于另一边没设。

**处理**
对每个镜头，视频(1)与音频(2)分别显式 set/clear：
```python
pi.setInPoint(sec, 1); pi.setOutPoint(sec, 1)   # 视频
pi.setInPoint(sec, 2); pi.setOutPoint(sec, 2)   # 音频
```
另外：清空时间线时**音频轨也要清**（只清 V1 会留下一堆旧音频）。
读取时也一样：`getInPoint(4)` 读的是视频入点、`getOutPoint(4)` 读的可能是音频出点 —— 混合读法非常坑。

---

## 一句话总结

前 8 条的共性是：**CEP 的报错信息与真实原因完全不匹配**。
遇到「面板没反应 / 全部 evalScript 失败 / 回调不来」，
先按本页顺序核对，比读官方文档快得多。
