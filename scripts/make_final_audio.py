# -*- coding: utf-8 -*-
"""拼完整音轨：人声从 0s 起 ＋ 可选 BGM（含闪避/淡出）。

⚠️ 2026-10-09 用户定：**孩子的复盘音频不要加 BGM**（孩子背的古诗才加）。
   所以本脚本默认 `WITH_BGM = False`；古诗那条管线才把它改成 True
   （并先跑 make_gain.py / make_bgm_full.py / make_bgm_mixed.py 产出 bgm_final.wav）。

为什么不在 ffmpeg 里 adelay：
  纯数字静音的 6 秒会被 AAC 丢弃 → 音频流 start_time 变成 6.0s，
  平台转码容易音画不同步。这里直接产出「从 0 秒就有内容」的完整音轨；
  不加 BGM 时，封面段补一层 **-80dB 的极低噪声**（听不见，但能让 AAC 保留帧）。
"""
import argparse
import subprocess
import sys
from pathlib import Path

import imageio_ffmpeg
import numpy as np
from scipy.io import wavfile

sys.dont_write_bytecode = True

HERE = Path(__file__).parent
FF = imageio_ffmpeg.get_ffmpeg_exe()
SR = 48000
INTRO = 0.0                      # 剪辑要求：人声从第 0 秒就开始（不与封面错开）
PEAK_LIMIT = 10 ** (-1.5 / 20)      # 限到 -1.5 dBTP
DITHER = 1e-4                       # 封面段的填充底噪（≈ -80dB，听不见）


def probe_duration(path: Path) -> float:
    """用 -f null - 解析 time= 拿音频时长（本机没有 ffprobe）。"""
    import re
    r = subprocess.run([FF, "-i", str(path), "-f", "null", "-"],
                       capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    m = re.findall(r"time=(\d+):(\d+):([\d.]+)", r.stderr)
    if not m:
        raise SystemExit(f"拿不到时长：{path}")
    h, mi, s = m[-1]
    return int(h) * 3600 + int(mi) * 60 + float(s)


def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit("失败:\n" + (r.stderr or "")[-2000:])


def main() -> None:
    global HERE
    ap = argparse.ArgumentParser(description="拼完整音轨：人声从 0s 起 + 可选 BGM + 限幅")
    ap.add_argument("--workdir", default=".", help="当天产物目录")
    ap.add_argument("--audio", default="", help="精剪音频，默认自动找 复盘_精剪*.mp3")
    ap.add_argument("--total", type=float, default=0.0,
                    help="视频总时长（秒）；留 0 则用音频时长 +0.1 自动定")
    ap.add_argument("--with-bgm", action="store_true", help="叠加 bgm_final.wav（朗读类才用）")
    ap.add_argument("--out", default="_final_audio.wav")
    a = ap.parse_args()
    HERE = Path(a.workdir).resolve()

    if a.audio:
        voice = Path(a.audio) if Path(a.audio).is_absolute() else HERE / a.audio
    else:
        cand = sorted(HERE.glob("复盘_精剪*.mp3"))
        if not cand:
            raise SystemExit(f"{HERE} 里找不到 复盘_精剪*.mp3，用 --audio 指定")
        voice = cand[-1]
    total = a.total or (probe_duration(voice) + 0.1)
    print(f"人声 {voice.name}  总时长 {total:.2f}s  BGM={a.with_bgm}")

    # 1) 人声统一响度到 -16 LUFS，并转 48k
    voc = HERE / "_voc.wav"
    run([FF, "-v", "error", "-y", "-i", str(voice),
         "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", str(SR),
         "-c:a", "pcm_s16le", str(voc)])
    sr_v, v = wavfile.read(voc)
    v = v.astype(np.float32) / 32768
    if v.ndim == 1:
        v = np.stack([v, v], axis=1)

    n = int(total * SR)
    off = int(INTRO * SR)
    out = np.zeros((n, 2), dtype=np.float32)

    if a.with_bgm:
        bgm48 = HERE / "_bgm48.wav"
        run([FF, "-v", "error", "-y", "-i", str(HERE / "bgm_final.wav"),
             "-ar", str(SR), "-c:a", "pcm_s16le", str(bgm48)])
        sr_b, b = wavfile.read(bgm48)
        b = b.astype(np.float32) / 32768
        if b.ndim == 1:
            b = np.stack([b, b], axis=1)
        out[:len(b)] += b[:n]
    else:
        # 封面段给一层听不见的底噪，避免"纯静音被 AAC 丢掉"
        rng = np.random.default_rng(0)
        out[:off] += rng.normal(0, DITHER, (off, 2)).astype(np.float32)

    m = min(len(v), n - off)
    out[off:off + m] += v[:m]

    peak = float(np.max(np.abs(out)))
    print("合成峰值 %.2f dB" % (20 * np.log10(peak + 1e-12)))
    if peak > PEAK_LIMIT:
        out *= PEAK_LIMIT / peak
        print("→ 限幅到 -1.5 dBTP，衰减 %.2f dB" % (20 * np.log10(PEAK_LIMIT / peak)))

    final = HERE / a.out
    wavfile.write(final, SR, (np.clip(out, -1, 1) * 32767).astype(np.int16))
    print("-> %s  %.1fs  BGM=%s" % (a.out, n / SR, a.with_bgm))


if __name__ == "__main__":
    main()
