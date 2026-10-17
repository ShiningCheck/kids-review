# -*- coding: utf-8 -*-
"""词级对齐重做字幕：用成片 ASR 的词级时间戳给逐字稿文本定时。

为什么不用 subtitle.py 的均分：
  它把一句的时间按字符数平分给各片，长句的后半片会漂 4~11 秒（实测）。
  这里改成 —— 把成片 ASR 的**字级时间**与逐字稿文本做字符级对齐，
  每片字幕的时间直接取该片首字/末字的真实发音时间。
"""
import argparse
import difflib
import json
import re
import sys
from pathlib import Path

sys.dont_write_bytecode = True

from config import load_profile, mask_privacy_text, privacy_beep_terms

PROFILE = load_profile()
VIDEO = PROFILE.get("video", {})
HERE = Path(__file__).parent
INTRO = 0.0                 # 当前人声从 0s 开始，封面字幕与语音同轴
PX, PY = 1440, 1080
FONT = VIDEO.get("subtitle_font", "YouZiKuLongCang")
FS = int(VIDEO.get("subtitle_font_size", 74))     # 龙藏体自适应后字号
OUTLINE = int(VIDEO.get("subtitle_outline", 6))
SHADOW = int(VIDEO.get("subtitle_shadow", 2))
MARGINV = int(VIDEO.get("subtitle_margin_v", 46))
MAXCHARS = int(VIDEO.get("subtitle_max_chars", 15))  # 一行最多字数

HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {PX}
PlayResY: {PY}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{FONT},{FS},&H00FFFFFF,&H000000FF,&H00000000,&H80000000,0,0,0,0,100,100,2,0,1,{OUTLINE},{SHADOW},2,70,70,{MARGINV},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

KEEP_PUNCT = set("，。！？、；：,.!?;:")
BREAKS = set("，。！？；：,.!?;:")


def keep(ch: str) -> bool:
    return bool(re.match(r"[\u4e00-\u9fff0-9a-zA-Z]", ch))


def ts(t: float) -> str:
    t = max(0.0, t)
    h = int(t // 3600)
    m = int(t % 3600 // 60)
    s = t % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def main() -> None:
    global HERE
    ap = argparse.ArgumentParser(description="按词级时间戳生成 ASS 字幕（文本取 edl 的 fix_text）")
    ap.add_argument("--workdir", default=".", help="当天产物目录（含 edl.json / v1_asr.json / verify/）")
    ap.add_argument("--force", action="store_true", help="跳过「edl 与 ASR 是否配套」校验")
    a = ap.parse_args()
    HERE = Path(a.workdir).resolve()

    edl = json.loads((HERE / "edl.json").read_text(encoding="utf-8-sig"))
    src = json.loads((HERE / "v1_asr.json").read_text(encoding="utf-8-sig"))["utterances"]
    fin = json.loads((HERE / "verify/v1_asr.json").read_text(encoding="utf-8-sig"))

    # ⚠️ 一致性校验：edl 的 keep_idx 是「按当时的 v1_asr 分句」记的索引。
    #    v1_asr.json 一旦被重新转写（比如另一次 transcribe 覆盖），分句变了、索引错位，
    #    字幕就会把「已删掉的句子」搬上屏——而且不报错（2026-10-17 实测踩到）。
    keep_text = {int(k): v for k, v in (edl.get("v1", {}).get("keep_text") or {}).items()}
    if keep_text and not a.force:
        bad = []
        for i, want in keep_text.items():
            if i >= len(src) or src[i]["text"] != want:
                bad.append((i, want, src[i]["text"] if i < len(src) else "(越界)"))
        if bad:
            print(f"!! edl 与 v1_asr.json 不配套，{len(bad)} 句对不上（前 3 条）：")
            for i, want, got in bad[:3]:
                print(f"   [{i}] edl 记的是：{want}")
                print(f"        现在读到的：{got}")
            raise SystemExit(
                "v1_asr.json 被重新转写过，索引已错位。\n"
                "修法：恢复出 edl 时用的那份 ASR，或重新定 KEEP 并重跑 cut_audio.py。\n"
                "确认数据没问题（如只是标点差异）可加 --force 跳过校验。")

    # 文本修正（--fix-text 的成果）从 edl 读：cut_audio 现在会写进 edl["v1"]["fix_text"]。
    # ⚠️ 之前这里写死空字典，导致 --fix-text 只改逐字稿、字幕仍是原始 ASR 文本
    #    （2026-10-16 踩到：「g」被 ASR 记成「歌歌」直接上了屏）。
    FIX = {int(k): v for k, v in (edl.get("v1", {}).get("fix_text") or {}).items()}
    sents = [FIX.get(i, src[i]["text"]) for i in edl["v1"]["keep_idx"]]
    subtitle_terms = edl.get("v1", {}).get(
        "pitch_words", privacy_beep_terms(PROFILE)
    )
    masked_sents = [mask_privacy_text(s, terms=subtitle_terms) for s in sents]
    changed = sum(a != b for a, b in zip(sents, masked_sents))
    if changed:
        print(f"隐私词遮盖 {changed} 句（与音频哔声保持一致）")
    sents = masked_sents

    # 成片 ASR 的字级时间
    vchars = []
    for w in fin["words"]:
        chs = [c for c in w["text"] if keep(c)]
        if not chs:
            continue
        t0, t1 = w["start"] / 1000, w["end"] / 1000
        for i, c in enumerate(chs):
            vchars.append((c, t0 + (t1 - t0) * i / len(chs),
                           t0 + (t1 - t0) * (i + 1) / len(chs)))

    # 目标：逐字稿的字符序列（保留标点用于断句，但不参与对齐）
    tgt = []          # (char, sent_idx)
    for si, s in enumerate(sents):
        for c in s:
            tgt.append((c, si))
    tgt_key = [c for c, _ in tgt if keep(c)]
    tgt_keep_idx = [n for n, (c, _) in enumerate(tgt) if keep(c)]
    v_key = [c for c, _, _ in vchars]

    times = [None] * len(tgt)         # 每个目标字符的 (start, end)
    ti = 0
    sm = difflib.SequenceMatcher(None, v_key, tgt_key, autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            for k in range(i2 - i1):
                a, b, _ = vchars[i1 + k]
                # 对应到 tgt 里的第 j1+k 个有效字符
                idx = tgt_keep_idx[j1 + k]
                times[idx] = (vchars[i1 + k][1], vchars[i1 + k][2])
        elif op in ("replace", "insert"):
            n = j2 - j1
            if n <= 0:
                continue
            idxs = tgt_keep_idx[j1:j2]
            if op == "replace" and i2 > i1:
                t0 = vchars[i1][1]
                t1 = vchars[i2 - 1][2]
            elif i1 < len(vchars):
                t0 = vchars[i1][1]
                t1 = vchars[min(i1 + 1, len(vchars) - 1)][2]
            else:
                t0 = vchars[-1][2]
                t1 = t0 + 0.3 * n
            for k, idx in enumerate(idxs):
                times[idx] = (t0 + (t1 - t0) * k / n, t0 + (t1 - t0) * (k + 1) / n)

    # 未对齐到的字符用前后最近的时间插值
    last = None
    for i in range(len(times)):
        if times[i] is not None:
            last = times[i][1]
        elif last is not None:
            times[i] = (last, last + 0.12)
            last += 0.12
    nxt = None
    for i in range(len(times) - 1, -1, -1):
        if times[i] is None:
            times[i] = (nxt - 0.12, nxt) if nxt else None
        else:
            nxt = times[i][0]
    for i in range(len(times)):
        if times[i] is None:                     # 极端情况兜底
            times[i] = (INTRO, INTRO + 0.3)

    # 分片：按句 → 按标点/长度切
    rows = []
    for si, s in enumerate(sents):
        idxs = [i for i, (c, sj) in enumerate(tgt) if sj == si]
        if not idxs:
            continue
        pieces, cur = [], []
        for k, i in enumerate(idxs):
            cur.append(i)
            ch = tgt[i][0]
            eff = len([x for x in cur if keep(tgt[x][0])])
            nxt = tgt[idxs[k + 1]][0] if k + 1 < len(idxs) else ""
            # 数字/英文串（如 5:30、bpmf）内部不能断
            ascii_run = bool(re.match(r"[0-9A-Za-z:.]", ch)) and \
                bool(re.match(r"[0-9A-Za-z:.]", nxt))
            if not ascii_run and (eff >= MAXCHARS or (ch in BREAKS and eff >= 4)):
                pieces.append(cur)
                cur = []
        if cur:
            pieces.append(cur)
        for p in pieces:
            chars = [i for i in p if keep(tgt[i][0])]
            if not chars:
                continue
            st = times[chars[0]][0]
            en = times[chars[-1]][1] + 0.18
            text = "".join(tgt[i][0] for i in p).strip()
            if text:
                rows.append([st, max(en, st + 0.7), text])

    # 防重叠 + 加封面偏移
    for i, r in enumerate(rows):
        if i and r[0] < rows[i - 1][1] + 0.06:
            r[0] = rows[i - 1][1] + 0.06
        if r[1] <= r[0]:
            r[1] = r[0] + 0.6
    rows = [[a + INTRO, b + INTRO, t] for a, b, t in rows]

    body = "".join(
        f"Dialogue: 0,{ts(a)},{ts(b)},Default,,0,0,0,,{t}\n" for a, b, t in rows)
    (HERE / "subs2.ass").write_text(HEAD + body, encoding="utf-8")
    print(f"字幕 {len(rows)} 条 -> subs2.ass")


if __name__ == "__main__":
    main()
