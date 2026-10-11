# -*- coding: utf-8 -*-
"""配置加载与环境准备。

设计原则
--------
项目相关的路径、序列名、分镜表结构全部来自 config.json，
代码里不出现任何绝对路径或项目专名 —— 这样换一个片子只需要改配置。
"""
import json
import os

# ---- 本机代理会连 127.0.0.1 也一起代理，必须让 pymiere 绕过 ----
_LOOPBACK = "127.0.0.1,localhost,::1"

DEFAULT_CONFIG_NAME = "config.json"


def prepare_environment():
    """必须在 import pymiere 之前调用。

    pymiere 内部用 requests 连 CEP 面板（http://127.0.0.1:3000）。
    如果本机设置了 HTTP_PROXY，requests 会把这个本地地址也代理出去，
    结果就是稳定超时 —— 而且在别的机器上极难定位。
    """
    for key in ("no_proxy", "NO_PROXY"):
        cur = os.environ.get(key, "")
        parts = [p for p in cur.split(",") if p.strip()]
        for h in _LOOPBACK.split(","):
            if h not in parts:
                parts.append(h)
        os.environ[key] = ",".join(parts)


class Config(object):
    """把 config.json 包装成好用的对象。"""

    def __init__(self, data, path):
        self.data = data
        self.path = os.path.abspath(path)
        self.root = os.path.dirname(self.path)

    # ---------- 路径 ----------
    def _abs(self, p):
        if not p:
            return ""
        return os.path.normpath(p if os.path.isabs(p) else os.path.join(self.root, p))

    @property
    def media_dir(self):
        return self._abs(self.data.get("media_dir"))

    @property
    def shotlist(self):
        return self._abs(self.data.get("shotlist"))

    @property
    def export_dir(self):
        return self._abs(self.data.get("export_dir") or "export")

    @property
    def export_preset(self):
        """.epr 预设路径；留空则用 PR 默认设置导出。"""
        return self._abs(self.data.get("export_preset")) if self.data.get("export_preset") else ""

    # ---------- 序列 ----------
    @property
    def sequences(self):
        """[{sheet, title, ascii_name}] —— ascii_name 用于建序列（见 README 坑 9）。"""
        out = []
        for s in self.data.get("sequences") or []:
            out.append({
                "sheet": s.get("sheet"),
                "title": s.get("title") or s.get("sheet"),
                "ascii_name": s.get("ascii_name") or "SEQ",
            })
        return out

    @property
    def preset_guid(self):
        return self.data.get("preset_guid") or "5e73dd7e-4f86-4917-80eb-08ddb2f4a5f3"

    # ---------- 分镜表列映射 ----------
    @property
    def columns(self):
        """分镜表的列顺序（0-based），默认适配常见的「分镜执行表」格式。"""
        c = self.data.get("columns") or {}
        return {
            "no": c.get("no", 0),
            "tc": c.get("tc", 1),
            "desc": c.get("desc", 2),
            "snd": c.get("snd", 3),
            "media": c.get("media", 4),
            "src_in": c.get("src_in", 5),
            "src_out": c.get("src_out", 6),
            "note": c.get("note", 7),
            "header_rows": c.get("header_rows", 2),
        }

    # ---------- 素材命名 ----------
    @property
    def proxy_suffix(self):
        return self.data.get("proxy_suffix") or "_Proxy"

    @property
    def project_name(self):
        return self.data.get("project_name") or "autocut"

    def resolve_shotlist(self):
        p = self.shotlist
        if not p or not os.path.isfile(p):
            raise SystemExit(
                "找不到分镜表：%s\n请编辑 config.json 的 shotlist 字段。" % (p or "(未配置)"))
        return p

    def resolve_media_dir(self):
        p = self.media_dir
        if not p or not os.path.isdir(p):
            raise SystemExit(
                "找不到素材目录：%s\n请编辑 config.json 的 media_dir 字段。" % (p or "(未配置)"))
        return p

    def __repr__(self):
        return "<Config %s>" % self.path


def load_config(path=None, start=None):
    """从指定路径或向上查找 config.json。"""
    if path:
        p = os.path.abspath(path)
    else:
        p = _find_up(start or os.getcwd())
    if not p or not os.path.isfile(p):
        raise SystemExit(
            "找不到 config.json。\n"
            "把 config.example.json 复制成 config.json 并改成你自己的路径：\n"
            "    cp config.example.json config.json")
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    return Config(data, p)


def _find_up(d):
    d = os.path.abspath(d)
    while True:
        cand = os.path.join(d, DEFAULT_CONFIG_NAME)
        if os.path.isfile(cand):
            return cand
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent