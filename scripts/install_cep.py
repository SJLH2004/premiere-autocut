# -*- coding: utf-8 -*-
"""安装/卸载 CEP 桥接扩展。

用法：
  python scripts/install_cep.py              # 安装（已存在则提示）
  python scripts/install_cep.py --force      # 覆盖安装
  python scripts/install_cep.py --uninstall  # 卸载
"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)))

from autocut import cep  # noqa: E402


def main():
    args = set(sys.argv[1:])
    if "--uninstall" in args:
        cep.uninstall()
        return 0
    cep.install(force="--force" in args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
