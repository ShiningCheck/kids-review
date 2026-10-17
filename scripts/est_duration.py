# -*- coding: utf-8 -*-
"""按 _drop.txt 估算成片时长（净语音 + 保留的自然停顿）

用法：
    $PY $S/est_duration.py [v1_asr.json] [_drop.txt]      # 默认各自同目录文件名

KEEP = 全集 - drop，这是唯一可靠的取法。
**不要**用正则去 mk_drop.py 里抠 KEEP 列表 —— 脚本注释里带数字和方括号
（如 `[137-141]`、`2+3=5`、`20-30`），正则抠出来必然混入这些数字，
估算直接偏小（2026-09-21 踩过：报 6.57 min，实际 9.4 min）。
"""
import json
import sys
from pathlib import Path

asr_p = Path(sys.argv[1] if len(sys.argv) > 1 else "v1_asr.json")
drop_p = Path(sys.argv[2] if len(sys.argv) > 2 else "_drop.txt")

u = json.loads(asr_p.read_text(encoding="utf-8-sig"))["utterances"]
raw = drop_p.read_text(encoding="utf-8-sig").replace("\n", ",")
drop_set = {int(x) for x in raw.split(",") if x.strip()}
KEEP = [i for i in range(len(u)) if i not in drop_set]

speech = sum(u[i]["end"] - u[i]["start"] for i in KEEP) / 1000.0
pauses = 0.0
prev = None
for i in KEEP:
    if prev is not None:
        gap = (u[i]["start"] - u[prev]["end"]) / 1000.0
        if 0 < gap <= 1.0:
            pauses += gap
    prev = i

print(f"共 {len(u)} 句，保留 {len(KEEP)}，删除 {len(drop_set)}")
print(f"净语音 {speech/60:.2f} min，保留停顿 {pauses:.1f}s")
print(f"预计成片 ≈ {(speech+pauses)/60:.2f} min"
      f"（实测一般再略高 0.3-0.6 min，cut_audio.py 段间回吸）")
