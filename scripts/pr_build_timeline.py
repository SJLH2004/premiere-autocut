# -*- coding: utf-8 -*-
"""用 pymiere 驱动 Premiere Pro 搭建时间线（通用版）。

工作流（标准代理剪辑流程）：
  1. 导入原片
  2. 挂代理，setEnableProxies(1) -> 剪辑时用代理，流畅
  3. 按分镜执行表铺镜头（自动计算时间线位置与源内入出点）
  4. 保存项目
  5. 导出前 setEnableProxies(0) -> 渲染走原片

前置条件：
  - Premiere Pro 2023+ 已启动，并已打开/新建一个项目
  - CEP 扩展已安装并加载：窗口 -> 扩展 -> Pymiere Link，显示「已就绪」
    （安装：python scripts/install_cep.py；自检：python scripts/probe.py）

用法：
  python scripts/pr_build_timeline.py --help
  python scripts/pr_build_timeline.py                # 只搭时间线
  python scripts/pr_build_timeline.py --wipe         # 先清空轨道再铺
  python scripts/pr_build_timeline.py --export       # 搭完并导出

所有项目相关的路径与序列名都来自 config.json —— 本文件不含任何绝对路径。
"""
import os
import re
import sys
import json
import argparse

# 必须在 import pymiere 之前完成：本机代理会把 127.0.0.1 也一起代理掉，
# 而 pymiere 用 requests 连本机的 CEP 面板，被代理就会稳定超时。
sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)))
from autocut.config import prepare_environment, load_config  # noqa: E402
from autocut.shots import parse_tc as _parse_tc, first_clip as _first_clip, load_shots as _load_shots  # noqa: E402

prepare_environment()

from openpyxl import load_workbook  # noqa: E402

# ---------------------------------------------------------------- 配置
CONFIG = load_config()
MEDIA = CONFIG.media_dir
COL = CONFIG.columns
PROXY_SUFFIX = CONFIG.proxy_suffix

print("[配置] %s" % CONFIG.path)
print("       素材目录: %s" % (MEDIA or "(未配置)"))
print("       分镜表  : %s" % (CONFIG.shotlist or "(未配置)"))


# ---------------------------------------------------------------- 读分镜表
def load_shots():
    """读取分镜表。解析逻辑在 autocut/shots.py（可独立测试）。"""
    return _load_shots(CONFIG.resolve_shotlist(), CONFIG.sequences, COL)


# ---------------------------------------------------------------- 找媒体文件
def find_media(clip):
    """返回 (原片路径, 代理路径)；用正斜杠，PR 在 Windows 上也认"""
    if not os.path.isdir(MEDIA):
        raise IOError("素材目录不可访问: %s" % MEDIA)

    orig = None
    for f in os.listdir(MEDIA):
        if not f.lower().startswith(clip.lower() + "."):
            continue
        if "_proxy" in f.lower():
            continue
        orig = os.path.join(MEDIA, f)
        break

    proxy = os.path.join(MEDIA, "%s%s.mp4" % (clip, PROXY_SUFFIX))
    if not os.path.isfile(proxy):
        proxy = None

    def slash(p):
        return p.replace("\\", "/") if p else None

    return slash(orig), slash(proxy)


def plan_shots(shots):
    """
    把分镜行展开成可执行计划：[(shot, tl, dur, src_in, src_out, confident), ...]

    v5 表里 20 个镜头只给了时间线位置、没给源内入出点。对这类镜头：
      confident=False -> 铺的时候不赌一段，而是按素材全长取 3 个候选起点，
      分层堆到 V1/V2/V3（+A1/A2/A3），由剪辑师在时间线上肉眼挑一段、删掉其余。
    """
    out = []
    for i, sh in enumerate(shots):
        if sh["clip"] is None:
            continue
        tl = sh["tl"] if sh["tl"] is not None else 0.0
        nxt = None
        for j in range(i + 1, len(shots)):
            if shots[j]["tl"] is not None:
                nxt = shots[j]["tl"]
                break
        dur = (nxt - tl) if (nxt is not None and nxt > tl) else 6.0

        confident = (sh["in"] is not None and sh["out"] is not None)
        if confident:
            src_in, src_out = sh["in"], sh["out"]
        else:
            src_in, src_out = 0.0, dur
        if src_out <= src_in:
            src_out = src_in + 0.5
        out.append((sh, tl, dur, src_in, src_out, confident))
    return out


def make_candidates(media_dur, dur, n=3):
    """
    源内入出点未知时，在素材上取 n 个候选起点（开头 / 中段 / 靠尾），每段长 dur。
    返回 (候选列表, 说明)。
    余量太小（素材只比镜头长一点点）时堆三层没有意义，只给 1 个候选。
    """
    if not media_dur or media_dur <= 0:
        return [(0.0, dur)], "素材时长未知，只用开头"
    span = min(dur, media_dur)
    slack = media_dur - span
    if slack < 2.0:
        return [(0.0, span)], ("素材 %.1fs / 镜头 %.1fs，余量仅 %.1fs，无可挑选空间"
                               % (media_dur, span, slack))
    last = slack
    if n <= 1:
        return [(0.0, span)], ""
    starts = [last * float(i) / (n - 1) for i in range(n)]
    seen, out = set(), []
    for s in starts:
        key = round(s, 2)
        if key in seen:
            continue
        seen.add(key)
        out.append((round(s, 2), round(s + span, 2)))
    return out, ("素材 %.1fs，%.1f~%.1f 三段可选" % (media_dur, 0.0, last))


def build_link_map(used):
    """
    代理 -> 原片 对照表。
    为什么需要：PR 2023 上 attachProxy() 恒返回 false、changeMediaPath() 会触发
    importer 通用错误并弹模态框（实测），脚本侧无法可靠切回原片。
    所以改为：剪辑版用代理，导出前用这份对照表在 PR 里「链接媒体」批量替换，
    或由 prproj_relink.py 直接改写 .prproj。
    """
    rows = []
    for c in used:
        o, p = find_media(c)
        rows.append({"clip": c, "proxy": p, "original": o})
    return rows


# ---------------------------------------------------------------- 主流程
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", action="store_true", help="搭完时间线后导出")
    ap.add_argument("--no-proxy", action="store_true", help="不附加代理（直接用原片）")
    ap.add_argument("--limit", type=int, default=0, help="每序列只铺前 N 镜（调试用）")
    ap.add_argument("--batch", type=int, default=8, help="每批导入多少条素材")
    ap.add_argument("--source", choices=["proxy", "original"], default="proxy",
                    help="用代理铺时间线(推荐,快)还是直接导入原片(慢)")
    ap.add_argument("--suffix", default="", help="序列名后缀，调试用（如 __test）")
    ap.add_argument("--try-attach", action="store_true",
                    help="（实验）尝试 attachProxy，实测恒返回 false，默认关")
    ap.add_argument("--wipe", action="store_true", help="铺之前先清空序列已有片段（含音频轨）")
    ap.add_argument("--no-stack", dest="stack", action="store_false",
                    help="入出点未知的镜头只铺一段（默认分层堆 3 个候选供挑选）")
    args = ap.parse_args()

    # 延迟导入，方便先跑 --help / 读表检查
    import pymiere
    from pymiere import wrappers, exe_utils
    from pymiere.core import check_premiere_is_alive

    print("=" * 62)
    print("%s · Premiere 时间线自动搭建" % CONFIG.project_name)
    print("=" * 62)

    # 0. 连接
    running, pid = exe_utils.is_premiere_running()
    if not running:
        print("\n[阻塞] Premiere Pro 没有运行。请先启动它。")
        return 2
    alive = check_premiere_is_alive(crash=False)
    if not alive:
        print("\n[阻塞] Premiere 已运行 (pid=%s)，但连不上桥接面板。请确认：" % pid)
        print("  窗口 -> 扩展 -> Pymiere Link，面板要显示「已就绪」")
        return 2

    print("\n[0] 已连接 Premiere (pid=%s)，版本 %s"
          % (pid, pymiere.objects.app.version))

    # 1. 读表
    seqs = load_shots()
    total = sum(len(s) for _, _, s in seqs)
    used = sorted({sh["clip"] for _, _, s in seqs for sh in s if sh["clip"]})
    print("[1] 读到 %d 个镜头，去重后需 %d 条素材" % (total, len(used)))

    # 2. 校验媒体
    want_proxy = (args.source == "proxy")
    missing_o, missing_p = [], []
    for c in used:
        o, p = find_media(c)
        if not o:
            missing_o.append(c)
        if not p:
            missing_p.append(c)
    if missing_o:
        print("[!] 缺原片: %s" % ", ".join(missing_o))
        return 3
    if want_proxy and missing_p:
        print("[!] 缺代理: %s" % ", ".join(missing_p))
        return 3
    print("[2] 原片 %d 条 / 代理 %d 条 全部就位；本次用【%s】铺时间线"
          % (len(used), len(used), "代理" if want_proxy else "原片"))

    # 2b. 落一份 代理->原片 对照表（导出前切回原片要用）
    linkmap = build_link_map(used)
    lm_path = os.path.join(CONFIG.root, "代理原片对照表.json").replace("\\", "/")
    with open(lm_path, "w", encoding="utf-8") as f:
        json.dump(linkmap, f, ensure_ascii=False, indent=2)
    print("    对照表已写入: %s" % lm_path)

    project = pymiere.objects.app.project

    # 3. 导入素材（分批：PR 2023 一次导太多会卡 UI，也便于定位哪条卡住）
    #    注意：这里只用 importFiles（实测可靠）。attachProxy / changeMediaPath
    #    在 PR 2023 脚本调用下会触发 importer 同步导入并弹「一般错误」模态框。
    paths = [find_media(c)[1 if want_proxy else 0] for c in used]

    # 幂等：先扫一遍项目里已有哪些素材，已经导入过的不再重复导入
    def norm_stem(p):
        s = os.path.splitext(os.path.basename(p or ""))[0]
        return s[:-len("_Proxy")] if s.lower().endswith("_proxy") else s

    def existing_stems():
        have = set()
        def w(item):
            try:
                kids = item.children
            except Exception:
                return
            for i in range(kids.numItems):
                it = kids[i]
                try:
                    if it.type == 2:
                        w(it); continue
                except Exception:
                    pass
                try:
                    mp = it.getMediaPath()
                except Exception:
                    mp = ""
                if mp:
                    have.add(norm_stem(mp))
        w(project.rootItem)
        return have

    already = existing_stems()
    todo = [p for p in paths if norm_stem(p) not in already]
    print("[3] 需导入 %d 条【%s】（已存在 %d 条，每批 %d 条）…"
          % (len(todo), "代理" if want_proxy else "原片", len(paths) - len(todo), args.batch))
    if todo:
        for i in range(0, len(todo), args.batch):
            chunk = todo[i:i + args.batch]
            print("    批次 %d/%d: %s"
                  % (i // args.batch + 1, (len(todo) + args.batch - 1) // args.batch,
                     ", ".join(os.path.basename(p) for p in chunk)))
            try:
                ok_import = project.importFiles(chunk, True, project.rootItem, False)
            except Exception as e:
                print("    [!] 本批导入异常: %s: %s" % (type(e).__name__, e))
                ok_import = False
            if not ok_import:
                print("    [!] importFiles 返回失败——PR 可能弹了对话框，请先处理再重跑")
    print("    导入阶段结束，项目内条目数 = %d" % project.rootItem.children.numItems)

    # 4. 建立 编号 -> projectItem 映射，并附加代理
    print("[4] 建立素材映射 + 附加代理…")
    idx = {}
    attached, skipped = 0, 0

    def walk(item):
        nonlocal attached, skipped
        try:
            kids = item.children
        except Exception:
            return
        for i in range(kids.numItems):
            it = kids[i]
            if it.type == 2:  # BIN
                walk(it)
                continue
            name = it.name
            try:
                mp = it.getMediaPath()
            except Exception:
                mp = ""
            if not mp:
                continue
            stem = os.path.splitext(os.path.basename(mp))[0]
            # 导入代理时文件名带 _Proxy 后缀，统一归一回素材编号
            is_proxy_item = stem.lower().endswith("_proxy")
            if is_proxy_item:
                stem = stem[:-len("_Proxy")]
            # 坑9：同一素材在项目里可能既有原片条目又有代理条目（手动导过就会），
            # 必须按本次要用的源来挑，不能"先到先得"，否则会误用原片（429MB）。
            if want_proxy:
                if is_proxy_item or stem not in idx:
                    idx[stem] = it
            else:
                if (not is_proxy_item) or stem not in idx:
                    idx[stem] = it

            if args.no_proxy:
                continue
            # 附加代理走 attachProxy 的路子已证实不可靠（恒 false / 弹框），
            # 默认跳过；如要尝试加 --try-attach
            if not args.try_attach:
                skipped += 1
                continue
            _, proxy = find_media(stem)
            if not proxy:
                continue
            try:
                if it.canProxy():
                    it.attachProxy(proxy, 0)   # 0 = 作为 proxy 附加
                    attached += 1
                else:
                    skipped += 1
            except Exception as e:
                print("    代理失败 %s: %s" % (stem, e))
                skipped += 1

    walk(project.rootItem)

    missing_map = [c for c in used if c not in idx]
    if missing_map:
        print("[!] 在项目里找不到: %s" % ", ".join(missing_map))
        return 5
    print("    映射 %d 条；已挂代理 %d 条，跳过 %d 条" % (len(idx), attached, skipped))

    # 5. 打开代理开关（仅当我们真的 attach 了代理时才有意义）
    if want_proxy:
        print("[5] 代理直接作为素材导入，无需开启「切换代理」（导出前靠对照表换回原片）")
    elif not args.no_proxy:
        pymiere.objects.app.setEnableProxies(1)
        print("[5] 已开启代理模式")

    # 6. 建序列 + 铺镜头
    def find_sequence(*names):
        """按名字找已有序列（精确或前缀），找不到返回 None"""
        try:
            n = len(project.sequences)
        except Exception:
            n = 0
        for i in range(n):
            try:
                s = project.sequences[i]
                nm = s.name
            except Exception:
                continue
            for want in names:
                if nm == want or nm.startswith(want):
                    return s
        return None

    js = []
    for seqname, asciiname, shots in seqs:
        full = (asciiname + args.suffix) if args.suffix else asciiname
        print("\n[6] 目标序列：%s（中文显示名 %s，%d 镜）" % (full, seqname, len(shots)))

        # 优先复用：PR 2023 的 createNewSequence 必然弹确认框，能不建就不建
        seq = find_sequence(full, seqname + args.suffix, seqname)
        if seq is not None:
            print("    复用已有序列")
        else:
            print("    新建序列（若 PR 弹出确认框，点一下「确定」即可）…")
            seq = project.createNewSequence(full, CONFIG.preset_guid)
            if seq is None:
                # 弹框点掉后序列其实已经建好了，再找一次
                seq = find_sequence(full, seqname)
            if seq is None:
                print("[!] 创建序列失败")
                return 6

        try:
            project.activeSequence = seq
        except Exception as e:
            print("    [warn] 设为活动序列失败: %s" % e)

        v1 = seq.videoTracks[0]
        try:
            existing = v1.clips.numItems
        except Exception:
            existing = 0

        if existing and args.wipe:
            # remove 必须给 2 个参数，否则报 Not Enough Parameters
            # 坑11：必须把音频轨也一起清！之前只清 V1，导致 insertClip 时代的
            # 旧音频残留，和新音频叠在一起，时间线被撑到 5 分钟。
            def wipe_track(tr, label):
                try:
                    n0 = tr.clips.numItems
                except Exception:
                    return 0
                k = 0
                for i in range(n0 - 1, -1, -1):
                    try:
                        tr.clips[i].remove(True, True)
                        k += 1
                    except Exception:
                        pass
                if n0:
                    print("    清空 %s：%d -> %d" % (label, n0, tr.clips.numItems))
                return k

            for vi in range(seq.videoTracks.numTracks):
                wipe_track(seq.videoTracks[vi], "V%d" % vi)
            for ai in range(seq.audioTracks.numTracks):
                wipe_track(seq.audioTracks[ai], "A%d" % ai)
            try:
                existing = v1.clips.numItems
            except Exception:
                existing = 0
            print("    清空完成，V1 现有 %d 个片段" % existing)

        if existing:
            print("    [!] 该序列 V1 已有 %d 个片段，跳过铺设（加 --wipe 可先清空）" % existing)
            js.append((full, seq))
            continue

        placed, gap, failed, stacked = 0, 0, [], []
        max_layer = min(seq.videoTracks.numTracks, seq.audioTracks.numTracks)
        if not args.stack:
            max_layer = 1

        for sh, tl, dur, src_in, src_out, confident in plan_shots(shots):
            if sh["clip"] is None:
                gap += 1
                continue
            pi = idx.get(sh["clip"])
            if pi is None:
                failed.append("镜%s 缺素材 %s" % (sh["no"], sh["clip"]))
                continue
            if args.limit and placed >= args.limit:
                break

            try:
                # mediaType 实测语义：1=视频，2=音频（互相独立，4 的读法是混合的）。
                # 必须两边都显式设，否则 overwriteClip 会把整条素材的音频糊进去。
                for m in (1, 2):
                    pi.clearInPoint(m)
                    pi.clearOutPoint(m)

                try:
                    media_dur = pi.getOutPoint(1).seconds
                except Exception:
                    media_dur = None

                if confident:
                    cands, note = [(src_in, src_out)], ""
                else:
                    # 入出点未知 -> 不赌一段，取 3 个候选分层堆上去让你挑
                    cands, note = make_candidates(media_dur, dur, n=max_layer)
                if len(cands) > 1:
                    stacked.append("镜%s %s（%d 个候选，分层 V1~V%d；%s）"
                                   % (sh["no"], sh["clip"], len(cands), len(cands), note))
                elif not confident:
                    stacked.append("镜%s %s（只有 1 个候选：%s）"
                                   % (sh["no"], sh["clip"], note))

                t = wrappers.time_from_seconds(tl)
                for layer, (a, b) in enumerate(cands):
                    if layer >= max_layer:
                        break
                    # clamp
                    if media_dur:
                        if b > media_dur:
                            b = media_dur
                        if a >= media_dur:
                            a = max(0.0, media_dur - 0.5)
                        if b <= a:
                            b = min(media_dur, a + 0.5)
                    pi.setInPoint(a, 1)
                    pi.setOutPoint(b, 1)
                    pi.setInPoint(a, 2)
                    pi.setOutPoint(b, 2)

                    # 坑10：必须用 overwriteClip（覆盖），不能用 insertClip（插入并后移）。
                    seq.videoTracks[layer].overwriteClip(pi, t)
                    if layer < seq.audioTracks.numTracks:
                        try:
                            seq.audioTracks[layer].overwriteClip(pi, t)
                        except Exception:
                            pass

                    for m in (1, 2):
                        pi.clearInPoint(m)
                        pi.clearOutPoint(m)

                placed += 1
            except Exception as e:
                failed.append("镜%s %s: %s" % (sh["no"], sh["clip"], e))
                for m in (1, 2):
                    try:
                        pi.clearInPoint(m)
                        pi.clearOutPoint(m)
                    except Exception:
                        pass

        print("    放置 %d 镜，字幕卡/空镜 %d 处，失败 %d，其中待定镜头 %d 个"
              % (placed, gap, len(failed), len(stacked)))
        for f in failed:
            print("      [!] %s" % f)
        for s in stacked:
            print("      [?] %s" % s)
        js.append((full, seq))

    # 7. 保存
    stem = "%s_%s" % (CONFIG.project_name, "proxy" if want_proxy else "original")
    save_to = os.path.join(CONFIG.root, "%s.prproj" % stem).replace("\\", "/")
    project.saveAs(save_to)
    print("\n[7] 项目已保存: %s" % save_to)

    # 8. 导出（可选）
    if args.export:
        print("\n[8] 导出前关闭代理 -> 渲染走原片")
        pymiere.objects.app.setEnableProxies(0)
        os.makedirs(CONFIG.export_dir, exist_ok=True)
        for seqname, seq in js:
            out = os.path.join(CONFIG.export_dir, "%s.mp4" % seqname).replace("\\", "/")
            print("    导出 %s -> %s" % (seqname, out))
            _ep = CONFIG.export_preset
            if _ep and os.path.isfile(_ep):
                seq.exportAsMediaDirect(out, _ep.replace("\\", "/"),
                                        pymiere.objects.app.encoder.ENCODE_ENTIRE)
            else:
                seq.exportAsMediaDirect(out, "", pymiere.objects.app.encoder.ENCODE_ENTIRE)
        print("    已提交导出（PR/AME 后台进行）")

    print("\n" + "=" * 62)
    print("完成。接下来你在 PR 里手动做：调节奏 / 转场 / 调色 / 字幕。")
    print("导出前记得：按钮「切换代理」关掉，或跑 --export 自动关。")
    print("=" * 62)
    return 0


if __name__ == "__main__":
    sys.exit(main())