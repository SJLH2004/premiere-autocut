# -*- coding: utf-8 -*-
"""环境自检。跑不通的时候先跑这个。"""
import os
import sys

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)))

from autocut import probe  # noqa: E402

if __name__ == "__main__":
    sys.exit(probe.run())
