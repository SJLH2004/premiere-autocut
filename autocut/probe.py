# -*- coding: utf-8 -*-
"""环境自检：在真正搭时间线之前，先把「为什么连不上」查清楚。

这个模块存在的意义：这条链路上有 5 个独立的失败点
（代理 / CEP 面板 / ExtendScript 引擎 / PR 版本 / 端口占用），
出错时的报错信息彼此很像。probe 逐项检查并明确告诉你是哪一环断了。
"""
import os
import socket
import sys

from .config import prepare_environment

PAINEL_URL = "http://127.0.0.1:3000"


def _check(name, fn):
    try:
        ok, detail = fn()
    except Exception as e:
        ok, detail = False, "%s: %s" % (type(e).__name__, e)
    mark = "OK  " if ok else "FAIL"
    print("  [%s] %-22s %s" % (mark, name, detail))
    return ok


def check_python():
    return True, "%s (%s)" % (sys.version.split()[0], sys.executable)


def check_pymiere():
    try:
        import pymiere  # noqa: F401
    except ImportError:
        return False, "未安装 —— 执行: pip install pymiere"
    ver = getattr(__import__("pymiere"), "__version__", None)
    return True, "已安装%s" % ((" " + ver) if ver else "")


def check_port():
    s = socket.socket()
    s.settimeout(2)
    try:
        s.connect(("127.0.0.1", 3000))
        s.close()
        return True, "127.0.0.1:3000 有响应（CEP 面板在跑）"
    except Exception:
        s.close()
        return False, "127.0.0.1:3000 无响应 —— 面板没加载，见 README"


def check_proxy():
    """最容易踩的坑：本机代理把 127.0.0.1 也代理掉。"""
    prepare_environment()
    bad = []
    for k in ("HTTP_PROXY", "http_proxy", "HTTPS_PROXY", "https_proxy"):
        if os.environ.get(k):
            bad.append(k)
    np = os.environ.get("no_proxy", "")
    if bad:
        return True, "检测到代理 %s；no_proxy=%s（已自动追加回环地址）" % (",".join(bad), np)
    return True, "无代理设置"


def check_premiere():
    try:
        import pymiere
        from pymiere import exe_utils
    except ImportError:
        return False, "pymiere 不可用，跳过"
    running, pid = exe_utils.is_premiere_running()
    if not running:
        return False, "Premiere 未在运行"
    return True, "Premiere 正在运行 (pid %s)" % pid


def check_evalscript():
    try:
        import pymiere
    except ImportError:
        return False, "pymiere 不可用，跳过"
    try:
        ver = pymiere.objects.app.version
    except Exception as e:
        return False, "evalScript 失败 —— %s" % e
    return True, "PR 版本 %s" % ver


STEPS = [
    ("Python", check_python),
    ("pymiere", check_pymiere),
    ("CEP 面板端口", check_port),
    ("代理设置", check_proxy),
    ("Premiere 进程", check_premiere),
    ("ExtendScript 链路", check_evalscript),
]


def run():
    print("=== premiere-autocut 环境自检 ===")
    print()
    results = [(name, _check(name, fn)) for name, fn in STEPS]
    print()
    failed = [n for n, ok in results if not ok]
    if not failed:
        print("全部通过，可以运行 scripts/pr_build_timeline.py")
        return 0
    print("以下环节未通过：%s" % "、".join(failed))
    print("对照 docs/troubleshooting.md 逐项排查。")
    return 1
