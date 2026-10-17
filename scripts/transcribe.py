"""步骤 1：抽音轨 → 火山 flash ASR 转写 → 逐字稿 JSON（分句 + 词级时间戳）

用法：
    python transcribe.py VID_a.mp4 [VID_b.mp4 ...] [-o 输出目录] [--frame]

产出（输出目录）：
    v1_16k.mp3   16k 单声道音轨
    v1_asr.json  {"text","duration_ms","utterances":[start,end,text],"words":[text,start,end]}
    v1_frame.jpg 首帧（--frame 时），供封面用

要点：
  - flash 接口支持 base64 直传，不需要公网 URL
  - 必须遍历所有 utterance 的 words，只看顶层会漏词
  - 必须过滤 start_time == -1，否则时间倒流
"""
import argparse
import base64
import json
import subprocess
import uuid
from pathlib import Path

import imageio_ffmpeg
import requests

from config import ENV_PATH, get_env, load_env

load_env()

ASR_BASE_URL = get_env(
    "ASR_BASE_URL",
    "https://openspeech.bytedance.com/api/v3/auc/bigmodel",
).rstrip("/")
FLASH = f"{ASR_BASE_URL}/recognize/flash"
RESOURCE = get_env("ASR_RESOURCE_ID", "volc.seedasr.auc")
TIMEOUT = float(get_env("ASR_TIMEOUT", "600"))
FF = imageio_ffmpeg.get_ffmpeg_exe()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("videos", nargs="+")
    ap.add_argument("-o", "--out", default=".")
    ap.add_argument("--frame", action="store_true", help="同时抽首帧（封面要用）")
    ap.add_argument("--frame-ss", default="1", help="抽首帧的时间点，秒")
    ap.add_argument("--tag", default=None,
                    help="输出前缀（单个输入时用，如 --tag day2 → day2_asr.json）")
    a = ap.parse_args()

    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    key = get_env("ASR_API_KEY", "")
    if not key:
        raise SystemExit(f"缺少 ASR_API_KEY，请编辑 {ENV_PATH} 或设置环境变量。")

    for i, src in enumerate(a.videos, 1):
        src = Path(src)
        tag = a.tag if (a.tag and len(a.videos) == 1) else f"v{i}"
        mp3 = out / f"{tag}_16k.mp3"
        js = out / f"{tag}_asr.json"

        if a.frame:
            fr = out / f"{tag}_frame.jpg"
            if not fr.exists():
                subprocess.run([FF, "-y", "-ss", a.frame_ss, "-i", str(src),
                                "-frames:v", "1", "-vf", "scale=640:-1", str(fr)],
                               capture_output=True)
                print(f"  {fr.name}")

        if not mp3.exists():
            print(f"{tag}: 抽音轨...", flush=True)
            subprocess.run([FF, "-y", "-i", str(src), "-vn", "-ar", "16000",
                            "-ac", "1", "-b:a", "64k", str(mp3)],
                           capture_output=True, check=True)

        print(f"{tag}: 转写中（{mp3.stat().st_size/1024/1024:.1f} MB）...", flush=True)
        r = requests.post(FLASH, headers={
            "x-api-key": key,
            "x-api-request-id": str(uuid.uuid4()),
            "x-api-resource-id": RESOURCE,
            "Content-Type": "application/json",
        }, json={
            "audio": {"data": base64.b64encode(mp3.read_bytes()).decode(),
                      "format": "mp3", "rate": 16000},
            "request": {"model_name": "bigmodel", "enable_itn": True, "enable_punc": True},
        }, timeout=TIMEOUT)

        if r.status_code != 200:
            print(f"  HTTP {r.status_code}: {r.text[:300]}")
            continue

        utts = r.json().get("result", {}).get("utterances", [])
        words = []
        for x in utts:
            for w in (x.get("words") or []):
                s, e, t = w.get("start_time"), w.get("end_time"), (w.get("text") or "").strip()
                if s is None or e is None or s < 0 or not t:
                    continue
                words.append({"text": t, "start": s, "end": e})
        words.sort(key=lambda w: w["start"])

        js.write_text(json.dumps({
            "text": r.json().get("result", {}).get("text", ""),
            "duration_ms": words[-1]["end"] if words else 0,
            "utterances": [{"start": x["start_time"], "end": x["end_time"],
                            "text": x["text"]} for x in utts],
            "words": words,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

        mins = words[-1]["end"] / 60000 if words else 0
        print(f"{tag}: 分句 {len(utts)}，词 {len(words)}，{mins:.1f} 分钟 -> {js.name}")


if __name__ == "__main__":
    main()
