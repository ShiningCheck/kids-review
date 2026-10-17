# -*- coding: utf-8 -*-
"""合成《我的一年级》视频：封面段 + 水彩背景 + 烧字幕 + 精剪音轨。

时间轴：
    0        - INTRO   封面（田字格标题卡；人声从 0s 就开始，与封面重叠）
    INTRO    - TOTAL   水彩画全屏背景 + 龙藏体字幕

音轨用 make_final_audio.py 产出的 _final_audio.wav（人声从 0s 起，
封面段垫 -80dB 底噪防 AAC 丢帧）。

用法：
    python build_video.py --workdir <当天目录> --date 2026-10-16 --out 我的一年级_20261016.mp4
"""
import argparse
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg

sys.dont_write_bytecode = True

from config import load_profile

PROFILE = load_profile()
VIDEO = PROFILE.get("video", {})
HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()


def probe_duration(path: Path) -> float:
    import re
    r = subprocess.run([FF, "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise SystemExit(f"拿不到时长：{path}")
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def main() -> int:
    global HERE
    ap = argparse.ArgumentParser(description="封面段 + 水彩背景 + 烧字幕 → 成片 mp4")
    ap.add_argument("--workdir", default=".", help="当天产物目录")
    ap.add_argument("--date", required=True, help="播出日期 YYYY-MM-DD（找封面用）")
    ap.add_argument("--cover", default="", help="封面图，默认 封面_<日期>.png")
    ap.add_argument("--bg", default="bg_1440.png", help="正文背景图（make_cover 产出的）")
    ap.add_argument("--ass", default="subs2.ass")
    ap.add_argument("--audio", default="_final_audio.wav")
    ap.add_argument("--out", default="", help="成片名，默认 我的一年级_<YYYYMMDD>.mp4")
    ap.add_argument("--intro", type=float,
                    default=float(VIDEO.get("intro_seconds", 6.0)),
                    help="封面停留秒数")
    ap.add_argument("--total", type=float, default=0.0, help="总时长；0 = 按音轨自动")
    ap.add_argument("--crf", default=str(VIDEO.get("crf", "20")))
    a = ap.parse_args()
    HERE = Path(a.workdir).resolve()

    cover = HERE / (a.cover or f"封面_{a.date.replace('-', '年', 1).replace('-', '月', 1)}日.png")
    bg = HERE / a.bg
    ass = HERE / a.ass
    audio = HERE / a.audio
    for p in (cover, bg, ass, audio):
        if not p.exists():
            raise SystemExit(f"缺文件：{p}")
    # ⚠️ 背景图必须和成片同尺寸（4:3），竖版封面覆写过就会在这里暴露
    try:
        from PIL import Image
        w, h = Image.open(bg).size
        if abs(w / h - 4 / 3) > 0.02:
            raise SystemExit(f"{bg.name} 是 {w}x{h}，不是 4:3 —— 多半被竖版封面覆写了，"
                             "重跑一次横版 make_cover")
    except ImportError:
        pass

    total = a.total or probe_duration(audio)
    out = HERE / (a.out or f"我的一年级_{a.date.replace('-', '')}.mp4")
    ass_esc = str(ass).replace("\\", "/").replace(":", "\\:")

    fc = (
        "[0:v]fps=15,setsar=1,format=yuv420p,"
        f"trim=duration={a.intro},setpts=PTS-STARTPTS[v0];"
        "[1:v]fps=15,format=yuv420p,"
        f"trim=duration={total - a.intro:.2f},setpts=PTS-STARTPTS[v1];"
        "[v0][v1]concat=n=2:v=1:a=0[vcat];"
        # ⚠️ 字幕必须加在 concat 之后：0-INTRO 的封面段也有字幕，且与语音同轴
        f"[vcat]ass='{ass_esc}'[vout];"
        "[2:a]anull[aout]"
    )
    cmd = [
        FF, "-y", "-loglevel", "error",
        "-loop", "1", "-framerate", "15", "-i", str(cover),
        "-loop", "1", "-framerate", "15", "-i", str(bg),
        "-i", str(audio),
        "-filter_complex", fc,
        "-map", "[vout]", "-map", "[aout]",
        "-c:v", "libx264", "-crf", a.crf, "-preset", "veryfast",
        "-pix_fmt", "yuv420p", "-r", "15",
        "-c:a", "aac", "-b:a", "192k", "-ar", "48000",
        "-movflags", "+faststart",
        "-t", f"{total}",
        str(out),
    ]
    print(f"合成中（15fps，{total:.1f}s）...", flush=True)
    log = HERE / "render.log"
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run(cmd, cwd=str(HERE), stdout=f, stderr=f)
    if r.returncode != 0:
        tail = log.read_text(encoding="utf-8", errors="replace")[-2000:]
        raise SystemExit("合成失败：\n" + tail)
    print("成片 ->", out.name, f"{out.stat().st_size / 1024 / 1024:.1f} MB", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
