# -*- coding: utf-8 -*-
"""
PR API 探针：用一条真实素材，实测 importFiles / attachProxy /
setInPoint / getInPoint / insertClip 在 PR 2023 上的真实行为。
探针序列最后会 deleteSequence 删掉，不污染项目。
"""
import os
import sys

os.environ["no_proxy"] = "127.0.0.1,localhost"
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

sys.path.insert(0, os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir)))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pr_build_timeline as P


def main():
    import pymiere
    from pymiere import wrappers, exe_utils
    from pymiere.core import check_premiere_is_alive

    running, pid = exe_utils.is_premiere_running()
    if not running:
        print("PR 没运行"); return 2
    if not check_premiere_is_alive(crash=False):
        print("连不上面板"); return 2
    print("connected pid=%s v%s" % (pid, pymiere.objects.app.version))

    clip = "DSC_6401"
    orig, proxy = P.find_media(clip)
    print("orig  :", orig)
    print("proxy :", proxy)

    project = pymiere.objects.app.project

    print("\n-- importFiles --")
    ok = project.importFiles([orig], True, project.rootItem, False)
    print("importFiles ->", ok)

    # 找到刚导入的 item
    pi = None
    kids = project.rootItem.children
    print("rootItem children:", kids.numItems)
    for i in range(kids.numItems):
        it = kids[i]
        mp = ""
        try:
            mp = it.getMediaPath()
        except Exception:
            pass
        print("   [%d] %s type=%s media=%s" % (i, it.name, it.type, mp))
        if clip.lower() in (it.name or "").lower():
            pi = it
    if pi is None:
        print("!! 没找到导入的 item"); return 3

    print("\n-- proxy --")
    print("canProxy ->", pi.canProxy())
    try:
        print("attachProxy ->", pi.attachProxy(proxy, 0))
        print("hasProxy ->", pi.hasProxy())
        print("getProxyPath ->", pi.getProxyPath())
    except Exception as e:
        print("attachProxy 失败:", type(e).__name__, e)

    print("\n-- mediaType 试值（setInPoint(3.28, N) / getInPoint(N)）--")
    for mt in (1, 2, 3, 4):
        try:
            pi.setInPoint(3.28, mt)
            got = pi.getInPoint(mt)
            print("   mediaType=%s -> getInPoint=%s" % (mt, got.seconds))
        except Exception as e:
            print("   mediaType=%s -> 失败 %s" % (mt, e))
        try:
            pi.clearInPoint(mt)
        except Exception as e:
            print("   clearInPoint(%s) 失败 %s" % (mt, e))

    print("\n-- 探针序列：setInPoint/out + insertClip --")
    seq = project.createNewSequence("__probe_seq", P.PRESET)
    if seq is None:
        print("!! 建序列失败"); return 4
    print("createNewSequence ->", seq.name)
    project.activeSequence = seq
    print("videoTracks:", seq.videoTracks.numTracks)

    v1 = seq.videoTracks[0]
    pi.setInPoint(3.28, 4)
    pi.setOutPoint(8.82, 4)
    print("source in/out =", pi.getInPoint(4).seconds, pi.getOutPoint(4).seconds)

    t = wrappers.time_from_seconds(0.0)
    print("insertClip ->", v1.insertClip(pi, t))
    pi.clearInPoint(4)
    pi.clearOutPoint(4)

    print("trackItems:", v1.clips.numItems)
    for i in range(v1.clips.numItems):
        c = v1.clips[i]
        try:
            print("   clip %d start=%s end=%s in=%s out=%s dur=%s"
                  % (i, c.start.seconds, c.end.seconds,
                     c.inPoint.seconds, c.outPoint.seconds,
                     (c.end.seconds - c.start.seconds)))
        except Exception as e:
            print("   clip %d 读失败 %s" % (i, e))

    print("\n-- 删除探针序列 --")
    try:
        print("deleteSequence ->", project.deleteSequence(seq))
    except Exception as e:
        print("deleteSequence 失败:", type(e).__name__, e)

    print("\n探针结束（未保存项目）")
    return 0


if __name__ == "__main__":
    sys.exit(main())