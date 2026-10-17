# -*- coding: utf-8 -*-
"""《我的一年级》一条命令出片：封面 → 字幕 → 音轨 → 成片 → 竖版封面。

前置（kids-review-editing 阶段一已经产出，都在当天目录里）：
    复盘_精剪_<日期>.mp3    cut_audio.py 的成片音频
    edl.json               剪辑单（make_subs 会从这里读 fix_text 修正字幕文本）
    v1_asr.json            源 ASR
    verify/v1_asr.json     成片复检转写（字幕的时间锚点）
    bg_src.jpg             当天美术课水彩画（也可用 --bg 指定别处）

顺序很重要：
  ★ 横版封面先出（顺带写 bg_1440.png 作为正文背景）→ 渲染 → **最后**才出竖版封面。
    竖版封面如果也写 bg_1440.png，渲染会直接崩（2026-10-12 / 10-16 各踩一次）。

用法：
    python make_video.py --workdir work/20261016 --date 2026-10-16
    python make_video.py --workdir work/20261016 --date 2026-10-16 --no-vertical
    python make_video.py --workdir work/20261016 --date 2026-10-16 --skip-render  # 只验前半段
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent

from config import load_profile

PROFILE = load_profile()
VIDEO = PROFILE.get("video", {})


def cn_date(date: str) -> str:
    y, m, d = date.split("-")
    return f"{y}年{int(m)}月{int(d)}日"


def step(name: str) -> None:
    print(f"\n=== {name}", flush=True)


def run(args: list) -> None:
    cmd = [sys.executable, "-B"] + args
    print("  $", " ".join(Path(x).name if i else x for i, x in enumerate(args)))
    r = subprocess.run(cmd)
    if r.returncode != 0:
        raise SystemExit(f"步骤失败（rc={r.returncode}）：{args[0]}")


def main() -> int:
    ap = argparse.ArgumentParser(description="《我的一年级》封面+字幕+成片一键出片")
    ap.add_argument("--workdir", required=True, help="当天产物目录")
    ap.add_argument("--date", required=True, help="播出日期 YYYY-MM-DD")
    ap.add_argument("--bg", default="", help="水彩画路径，默认 <workdir>/bg_src.jpg")
    ap.add_argument("--line1", default=VIDEO.get("title_line1", "我的一年级"))
    ap.add_argument("--line2", default=VIDEO.get("title_line2", "第一学期"))
    ap.add_argument("--line3", default="", help="留空按日期自动生成「10.16 周五」")
    ap.add_argument("--font", default="", help="封面字体文件路径；留空用 profile 或自动查找")
    ap.add_argument("--out", default="", help="成片名，默认 我的一年级_<YYYYMMDD>.mp4")
    ap.add_argument("--intro", type=float, default=float(VIDEO.get("intro_seconds", 6.0)))
    ap.add_argument("--skip-render", action="store_true", help="只做封面/字幕/音轨，不渲染")
    ap.add_argument("--no-vertical", action="store_true", help="不出竖版封面")
    a = ap.parse_args()

    wd = Path(a.workdir).resolve()
    cn = cn_date(a.date)
    yy = a.date.replace("-", "")
    bg = Path(a.bg) if a.bg else wd / "bg_src.jpg"

    need = ["edl.json", "v1_asr.json", "verify/v1_asr.json"]
    miss = [n for n in need if not (wd / n).exists()]
    if not list(wd.glob("复盘_精剪*.mp3")):
        miss.append("复盘_精剪*.mp3")
    if not bg.exists():
        miss.append(str(bg))
    if miss:
        raise SystemExit("缺前置产物：\n  " + "\n  ".join(miss)
                         + "\n\n阶段一（转写 → 定删留 → cut_audio → verify 三连检）先跑完。")

    # 1) 横版封面 + 正文背景
    step("1/5 横版封面（1440x1080）+ 正文背景 bg_1440.png")
    run([str(HERE / "make_cover.py"), "--workdir", str(wd), "--date", a.date,
         "--bg", str(bg), "--size", "1440x1080",
         "--out", f"封面_{cn}.png", "--line1", a.line1, "--line2", a.line2,
         "--line3", a.line3, "--font", a.font])

    # 2) 字幕（文本取 edl 的 fix_text）
    step("2/5 字幕 subs2.ass")
    run([str(HERE / "make_subs.py"), "--workdir", str(wd)])

    # 3) 完整音轨（人声从 0s 起）
    step("3/5 音轨 _final_audio.wav")
    run([str(HERE / "make_final_audio.py"), "--workdir", str(wd)])

    # 4) 渲染
    out_name = a.out or f"我的一年级_{yy}.mp4"
    if a.skip_render:
        step("4/5 跳过渲染（--skip-render）")
    else:
        step("4/5 渲染成片")
        run([str(HERE / "build_video.py"), "--workdir", str(wd), "--date", a.date,
             "--out", out_name, "--intro", str(a.intro)])

    # 5) 竖版封面（★ 必须最后，且 --no-bg）
    if a.no_vertical:
        step("5/5 跳过竖版封面（--no-vertical）")
        vcover = None
    else:
        step("5/5 竖版封面（1080x1920，--no-bg 保护 bg_1440.png）")
        vcover = wd / f"封面_竖版_{cn}.png"
        run([str(HERE / "make_cover.py"), "--workdir", str(wd), "--date", a.date,
             "--bg", str(bg), "--size", "1080x1920",
             "--out", vcover.name, "--line1", a.line1, "--line2", a.line2,
             "--line3", a.line3, "--font", a.font, "--no-bg"])

    print("\n=== 产物")
    for p in (wd / f"封面_{cn}.png", wd / "subs2.ass", wd / "_final_audio.wav",
              wd / out_name, vcover):
        if p and p.exists():
            print(f"  {p.name}  {p.stat().st_size / 1024 / 1024:.2f} MB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
