# -*- coding: utf-8 -*-
"""生成示例分镜执行表。

不把 .xlsx 直接提交进仓库，而是提供生成脚本 —— 二进制文件不便 review，
且不同 Excel 版本可能产生无意义的差异。需要时跑一次即可：

    python examples/make_example.py

生成的 shotlist.example.xlsx 列结构与「分镜执行表」一致，
对应 config.example.json 里的 columns 映射。
"""
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "shotlist.example.xlsx")

HEADER = ["镜号", "时间码", "画面描述", "声音", "素材", "源入点", "源出点", "备注"]

SHEETS = {
    "上部": [
        (1, "0:00-0:05", "开场 空镜 晨雾", "风声音效", "CLIP_0001 / CLIP_0002", 2.0, 7.0, ""),
        (2, "0:05-0:12", "主角 特写 起手", "背景音乐起", "CLIP_0005", None, None, "入出点待定"),
        (3, "0:12-0:19", "中景 对练", "拳风声", "CLIP_0008 / 0009", 1.5, 8.5, ""),
        (4, "0:19-0:24", "字幕卡", "", "", None, None, "黑场留空"),
        (5, "0:24-0:32", "远景 收势", "音乐渐弱", "CLIP_0012", 0.0, 8.0, ""),
    ],
    "下部": [
        (1, "0:00-0:06", "空镜 屋檐", "环境声", "CLIP_0020", 1.0, 7.0, ""),
        (2, "0:06-0:15", "近景 手部动作", "鼓点", "CLIP_0021 / 0022", None, None, "入出点待定"),
    ],
}


def main():
    from openpyxl import Workbook
    wb = Workbook()
    first = True
    for sheet, rows in SHEETS.items():
        ws = wb.active if first else wb.create_sheet()
        ws.title = sheet
        first = False
        # 第 1 行表头，第 2 行留空（对应 columns.header_rows = 2）
        ws.append(HEADER)
        ws.append([""] * len(HEADER))
        for r in rows:
            ws.append(list(r))
    wb.save(OUT)
    print("已生成: %s (%d 字节)" % (OUT, os.path.getsize(OUT)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
