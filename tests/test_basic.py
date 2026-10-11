# -*- coding: utf-8 -*-
"""基础自测 —— 不需要 Premiere，也不需要 pymiere。

覆盖：时间码解析、素材名提取、列映射、示例分镜表读取、配置加载。
用法：python tests/test_basic.py   （退出码 0 = 全部通过）
"""
import os
import sys
import traceback

# Windows 的控制台默认是 cp1252 之类的非 UTF-8 编码，直接 print 中文会抛
# UnicodeEncodeError 并让整个自测以退出码 1 结束（Linux/macOS 默认 UTF-8 不会）。
# CI 在 windows-latest 上必踩，所以这里强制改掉，并容错处理无法编码的字符。
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, os.pardir))
sys.path.insert(0, ROOT)

from autocut.shots import parse_tc, first_clip, to_float, parse_row, load_shots  # noqa: E402
from autocut import config as cfgmod  # noqa: E402

PASS = []
FAIL = []


def check(name, cond, detail=""):
    if cond:
        PASS.append(name)
        print("  PASS  %-46s %s" % (name, detail))
    else:
        FAIL.append(name)
        print("  FAIL  %-46s %s" % (name, detail))


def main():
    print("===== premiere-autocut 自测 =====")

    # ---------- 时间码 ----------
    print("\n-- 时间码解析 --")
    check("0:12-0:19 -> 12.0", parse_tc("0:12-0:19") == 12.0)
    check("1:04-1:10 -> 64.0", parse_tc("1:04-1:10") == 64.0)
    check("带空格", parse_tc("  0:05 - 0:12 ") == 5.0)
    check("小数秒 0:07.5-0:10", parse_tc("0:07.5-0:10") == 7.5)
    check("非法输入 -> None", parse_tc("") is None and parse_tc(None) is None)