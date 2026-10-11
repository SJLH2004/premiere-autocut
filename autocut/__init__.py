# -*- coding: utf-8 -*-
"""premiere-autocut —— 用 Python 实时控制 Premiere Pro 搭建时间线。

这个包只负责「环境准备 + 配置加载」，实际的重活由 scripts/ 下的脚本完成，
这样脚本仍可单独运行（便于调试），同时又能被 import 复用。
"""

__version__ = "0.1.0"

from .config import Config, load_config, prepare_environment  # noqa: F401
