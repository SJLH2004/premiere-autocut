# -*- coding: utf-8 -*-
"""基础自测 —— 不需要 Premiere，也不需要 pymiere。

覆盖：时间码解析、素材名提取、列映射、示例分镜表读取、配置加载。
用法：python tests/test_basic.py   （退出码 0 = 全部通过）
"""
import os
import sys
import traceback

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
    check("纯数字不算时间码", parse_tc("12") is None)

    # ---------- 素材名 ----------
    print("\n-- 素材名提取 --")
    check("取斜杠前第一个", first_clip("CLIP_6008 / 6030 / 6068") == "CLIP_6008")
    check("两个完整名", first_clip("DJI_0085 / DJI_0086") == "DJI_0085")
    check("单个名", first_clip("CLIP_0001") == "CLIP_0001")
    check("空白 -> None", first_clip("   ") is None)
    check("空 -> None", first_clip(None) is None)

    # ---------- 数值 ----------
    print("\n-- 数值转换 --")
    check("float 字符串", to_float("2.5") == 2.5)
    check("int", to_float(3) == 3.0)
    check("None 保持", to_float(None) is None)
    check("乱码 -> None", to_float("待定") is None)

    # ---------- 列映射 ----------
    print("\n-- 列映射（0-based）--")
    cols = {"no": 0, "tc": 1, "desc": 2, "snd": 3, "media": 4,
            "src_in": 5, "src_out": 6, "note": 7, "header_rows": 2}
    row = (1, "0:00-0:05", "开场空镜", "风声", "CLIP_0001 / CLIP_0002", 2.0, 7.0, "")
    s = parse_row(row, cols)
    check("镜号", s["no"] == 1)
    check("时间线起点", s["tl"] == 0.0)
    check("素材名", s["clip"] == "CLIP_0001")
    check("源入点", s["in"] == 2.0)
    check("源出点", s["out"] == 7.0)
    check("描述", s["desc"] == "开场空镜")
    s2 = parse_row((4, "0:19-0:24", "字幕卡", "", "", None, None, "黑场留空"), cols)
    check("无素材镜头 clip=None", s2["clip"] is None)
    # 自定义列顺序：把素材列换到第 3 列
    cols_b = dict(cols, media=3, snd=4)
    s3 = parse_row((1, "0:00", "d", "CLIP_0009", "snd", 1.0, 2.0, ""), cols_b)
    check("自定义列映射生效", s3["clip"] == "CLIP_0009")

    # ---------- 示例分镜表 ----------
    print("\n-- 示例分镜表读取 --")
    xlsx = os.path.join(ROOT, "examples", "shotlist.example.xlsx")
    if not os.path.isfile(xlsx):
        # 示例表不入库，测试时现场生成（需要 openpyxl）
        try:
            sys.path.insert(0, os.path.join(ROOT, "examples"))
            import make_example
            make_example.main()
        except Exception as e:
            print("  (无法生成示例表: %s)" % e)
    check("示例表可用", os.path.isfile(xlsx), xlsx)
    if os.path.isfile(xlsx):
        try:
            seqs = load_shots(xlsx, [
                {"sheet": "上部", "title": "A_上部", "ascii_name": "SEQ_A"},
                {"sheet": "下部", "title": "B_下部", "ascii_name": "SEQ_B"},
            ], cols)
            check("读到 2 个序列", len(seqs) == 2)
            a = seqs[0][2]
            check("上部镜头数", len(a) == 5, "%d 个" % len(a))
            check("首个镜头素材", a[0]["clip"] == "CLIP_0001")
            check("第 2 镜入出点未知", a[1]["in"] is None and a[1]["out"] is None)
            check("字幕卡 clip=None", a[3]["clip"] is None)
            check("序列中文名", seqs[0][0] == "A_上部")
            check("序列 ASCII 名", seqs[0][1] == "SEQ_A")
            check("下部镜头数", len(seqs[1][2]) == 2)
            check("表头跳过正确（首镜是 1 不是表头）", str(a[0]["no"]) == "1")
        except Exception:
            check("示例表读取", False, traceback.format_exc()[-200:])
        try:
            load_shots(xlsx, [{"sheet": "不存在的表", "title": "x", "ascii_name": "x"}], cols)
            check("缺失工作表应报错", False, "没有抛异常")
        except KeyError as e:
            check("缺失工作表报错信息清晰", "不存在的表" in str(e))

    # ---------- 配置 ----------
    print("\n-- 配置加载 --")
    example = os.path.join(ROOT, "config.example.json")
    check("config.example.json 存在", os.path.isfile(example))
    if os.path.isfile(example):
        c = cfgmod.load_config(example)
        check("项目名", c.project_name == "myfilm", c.project_name)
        check("素材目录已归一化", os.path.isabs(c.media_dir))
        check("序列数", len(c.sequences) == 2)
        check("预设 GUID 有默认值", len(c.preset_guid) == 36, c.preset_guid)
        check("代理后缀", c.proxy_suffix == "_Proxy")
        check("列映射完整", set(["no", "tc", "media", "src_in", "src_out"]).issubset(c.columns))
        check("export_dir 已解析", os.path.isabs(c.export_dir))
    # 向上查找
    found = cfgmod._find_up(ROOT)
    check("向上查找 config.json", found is None or found.endswith("config.json"))

    # ---------- 环境准备 ----------
    print("\n-- 环境准备 --")
    os.environ.pop("no_proxy", None)
    os.environ.pop("NO_PROXY", None)
    cfgmod.prepare_environment()
    check("no_proxy 含 127.0.0.1", "127.0.0.1" in os.environ.get("no_proxy", ""))
    check("NO_PROXY 含 localhost", "localhost" in os.environ.get("NO_PROXY", ""))
    # 幂等
    cfgmod.prepare_environment()
    check("重复调用不重复追加", os.environ["no_proxy"].count("127.0.0.1") == 1)

    # ---------- 合规 ----------
    print("\n-- 合规自检 --")
    bad = []
    for dp, dn, fn in os.walk(ROOT):
        if ".git" in dp or "__pycache__" in dp:
            continue
        for name in fn:
            if name == "CSInterface.js":
                bad.append(os.path.join(dp, name))
            p = os.path.join(dp, name)
            if name.endswith((".js", ".jsx", ".py", ".html", ".xml")):
                try:
                    head = "".join(open(p, encoding="utf-8", errors="replace").readlines()[:40])
                except Exception:
                    continue
                if "ADOBE SYSTEMS INCORPORATED" in head or \
                   ("Copyright" in head and "All Rights Reserved" in head):
                    bad.append(p)
    check("仓库内无 Adobe 专有文件", not bad, ", ".join(bad[:3]))

    print("\n===== 结果：PASS %d / FAIL %d =====" % (len(PASS), len(FAIL)))
    if FAIL:
        for f in FAIL:
            print("  FAILED: %s" % f)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())