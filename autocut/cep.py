# -*- coding: utf-8 -*-
"""CEP 扩展的安装与卸载。

我们自研这个扩展的原因：官方 pymiere_link.zxp 在 GitHub 和各类镜像都已下不到，
而 pymiere 的 Python 端需要一个能执行 ExtendScript 的宿主面板。
"""
import os
import sys
import shutil

# Windows / macOS 的 CEP 扩展目录
WIN_EXT = r"C:\Program Files\Common Files\Adobe\CEP\extensions"
MAC_EXT = os.path.expanduser("~/Library/Application Support/Adobe/CEP/extensions")

EXTENSION_ID = "com.pymiere.link"
_ITEMS = ["CSXS", "js", "jsx", "index.html"]


def extension_root():
    if sys.platform.startswith("win"):
        return WIN_EXT
    return MAC_EXT


def target_dir():
    return os.path.join(extension_root(), EXTENSION_ID)


def source_dir():
    """仓库里 cep/ 的位置（相对本文件向上两级）。"""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.normpath(os.path.join(here, os.pardir, "cep"))


def install(force=False):
    src, dst = source_dir(), target_dir()
    if not os.path.isdir(src):
        raise SystemExit("找不到扩展源目录：%s" % src)
    if os.path.isdir(dst) and not force:
        print("目标已存在：%s" % dst)
        print("要覆盖请加 --force")
    else:
        os.makedirs(dst, exist_ok=True)
        for item in _ITEMS:
            s = os.path.join(src, item)
            if not os.path.exists(s):
                print("  [跳过] 源缺少 %s" % item)
                continue
            d = os.path.join(dst, item)
            if os.path.isdir(s):
                if os.path.isdir(d):
                    shutil.rmtree(d)
                shutil.copytree(s, d)
            else:
                shutil.copy2(s, d)
            print("  [复制] %s" % item)
        print("扩展已安装到：%s" % dst)

    enable_debug_mode()
    print()
    print("下一步：")
    print("  1. 重启 Premiere Pro")
    print("  2. 菜单 窗口 → 扩展 → Pymiere Link，面板应显示「已就绪」")
    print("  3. 运行  python scripts/probe.py  验证链路")


def enable_debug_mode():
    """写 CSXS.8 ~ CSXS.12 的 PlayerDebugMode 注册表项。

    说明：这一步是 Adobe 对未签名扩展的官方放行方式（面板调试模式）。
    这里用 Python 的 winreg，因为 reg.exe 常被安全软件拦截。
    """
    if not sys.platform.startswith("win"):
        print("非 Windows，跳过注册表（macOS 用 defaults write，见 README）")
        return
    try:
        import winreg
    except ImportError:
        print("[警告] 无法 import winreg，请手动设置 PlayerDebugMode")
        return
    for v in range(8, 13):
        sub = r"Software\Adobe\CSXS.%d" % v
        try:
            winreg.CreateKey(winreg.HKEY_CURRENT_USER, sub)
            k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, sub, 0, winreg.KEY_SET_VALUE)
            winreg.SetValueEx(k, "PlayerDebugMode", 0, winreg.REG_SZ, "1")
            winreg.CloseKey(k)
            print("  [注册表] CSXS.%d PlayerDebugMode=1" % v)
        except Exception as e:
            print("  [注册表] CSXS.%d 失败: %s" % (v, e))


def uninstall():
    dst = target_dir()
    if os.path.isdir(dst):
        shutil.rmtree(dst)
        print("已移除：%s" % dst)
    else:
        print("未安装：%s" % dst)
