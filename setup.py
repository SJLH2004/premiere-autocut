# -*- coding: utf-8 -*-
from setuptools import setup, find_packages

with open("README.md", encoding="utf-8") as f:
    long_desc = f.read()

setup(
    name="premiere-autocut",
    version="0.1.0",
    description="用 Python 实时驱动 Premiere Pro 搭建时间线（含自研 CEP 桥接扩展）",
    long_description=long_desc,
    long_description_content_type="text/markdown",
    packages=find_packages(),
    python_requires=">=3.8",
    install_requires=["pymiere>=1.4.0", "openpyxl>=3.0"],
    classifiers=[
        "Development Status :: 3 - Alpha",
        "Intended Audience :: End Users/Desktop",
        "Operating System :: Microsoft :: Windows",
        "Operating System :: MacOS",
        "Programming Language :: Python :: 3",
        "Topic :: Multimedia :: Video",
        "Topic :: Multimedia :: Video :: Non-Linear Editor",
    ],
)
