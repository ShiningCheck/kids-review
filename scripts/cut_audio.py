# -*- coding: utf-8 -*-
"""纯音频精剪（亲子复盘录音等）—— 按 utterance 索引删句 -> ffmpeg 剪 -> 逐字稿

    python cut_audio.py SRC.mp3 v1_asr.json --drop 2,3,4,5 -o 成片.mp3
                        [--sections sections.json] [--adult 0,16,33]
                        [--word-drop 77:423700-426260] [--fix-text "77=修剪后的整句"]
                        [--denoise light|mid|strong|off] [--no-loudnorm]

产出：edl.json / 成片.mp3 / 逐字稿.md

与 render.py（视频）的区别：
  - 用 atrim + concat + 每片 afade，不需要视频轨
  - 滤镜串很长（80+ 段），必须走 -filter_complex_script，否则撑爆命令行
"""
import argparse, json, re, subprocess
from pathlib import Path
import imageio_ffmpeg

from config import load_profile, privacy_beep_terms

PROFILE = load_profile()
FF = imageio_ffmpeg.get_ffmpeg_exe()
PAD = 0.08        # 词边界保护
KEEP_PAUSE = 1.0  # <=1s 的停顿保留（自然停顿，切了会急促）
PULLBACK = 0.5    # >1s 的停顿删掉，但回吸 0.5s 静音做呼吸
DENOISE = {
    "off": "",
    "light": "highpass=f=80,afftdn=nf=-30:nr=16",
    "mid": "highpass=f=80,afftdn=nf=-25:nr=24",
    "strong": "highpass=f=80,afftdn=nf=-22:nr=32",
}


def duration(path):
    r = subprocess.run([FF, "-i", path], capture_output=True, text=True, errors="ignore")
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", r.stderr)
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def source_date(src):
    """从源文件名取日期（YYYY年MM月DD日），没有就用文件修改时间"""
    m = re.search(r"(\d{4})年(\d{1,2})月(\d{1,2})日", Path(src).name)
    if m:
        y, mo, d = m.groups()
        return f"{y}年{int(mo):02d}月{int(d):02d}日"
    import datetime
    ts = Path(src).stat().st_mtime
    return datetime.datetime.fromtimestamp(ts).strftime("%Y年%m月%d日")


def mmss(x):
    return f"{int(x // 60):02d}:{int(x % 60):02d}"


def find_term(haystack: str, term: str, start: int = 0) -> int:
    """ASCII 词忽略大小写，避免 ASR 把英文名转成不同大小写后漏掉。"""
    if term.isascii():
        return haystack.lower().find(term.lower(), start)
    return haystack.find(term, start)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("asr")
    ap.add_argument("--drop", required=True, help="要删的 utterance 索引，逗号分隔")
    ap.add_argument("-o", "--out", default=None,
                    help="成片文件名，默认 复盘_精剪_<源文件日期>.mp3")
    ap.add_argument("--sections", help='JSON: [[起,止,"小节名"], ...]')
    ap.add_argument("--adult", default="", help="大人说的 utterance 索引，逗号分隔")
    ap.add_argument("--plain", action="store_true",
                    default=PROFILE["editing"].get("plain_transcript", True),
                    help="逐字稿只要说话内容，不带时间戳和说话人标注")
    ap.add_argument("--no-render", action="store_true",
                    help="跳过 ffmpeg 渲染，只重新生成逐字稿（成片已存在时用）")
    ap.add_argument("--denoise", default=PROFILE["editing"].get("denoise", "light"))
    ap.add_argument("--no-loudnorm", action="store_true",
                    default=not PROFILE["editing"].get("loudnorm", True))
    ap.add_argument("--pitch", default="",
                    help="要整句变音的 utterance 索引，逗号分隔")
    ap.add_argument("--pitch-words", default=",".join(privacy_beep_terms(PROFILE)),
                    help="只变音这些词（词级定位，推荐）：逗号分隔，如 孩子姓名,学校名。"
                         "同一词的多种写法都列上（ASR 可能听成同音字）")
    ap.add_argument("--pitch-factor", type=float,
                    default=float(PROFILE["editing"].get("pitch_factor", 1.3)),
                    help="变音升降调倍率，>1 升调（默认 1.3）")
    ap.add_argument("--pitch-mode",
                    default=PROFILE["editing"].get("privacy_mode", "beep"),
                    choices=["pitch", "beep"],
                    help="pitch=变调（保留语句可懂度）；beep=用 1kHz 哔声遮盖（彻底听不出词）")
    ap.add_argument("--word-drop", default="",
                    help="句内词级删冗（重复/口吃）：`idx:起ms-止ms`，多条用逗号分隔，"
                         "如 77:423700-426260。区间取**源录音时间轴**，可用 ASR 的 "
                         "words 词级时间戳定位")
    ap.add_argument("--fix-text", default="",
                    help="逐字稿文字改写：`idx=修剪后的整句`，多条用 | 分隔，"
                         "如 77=不过他有点累，还需要休息一下，…。"
                         "配合 --word-drop 用，让逐字稿和音频一致")
    a = ap.parse_args()

    drop = sorted({int(x) for x in a.drop.split(",") if x.strip()})
    adult = {int(x) for x in a.adult.split(",") if x.strip()}
    pitch = {int(x) for x in a.pitch.split(",") if x.strip()}
    pitch_words = [x for x in a.pitch_words.split(",") if x.strip()]
    sections = json.loads(Path(a.sections).read_text(encoding="utf-8-sig")) if a.sections else []
    sections = [tuple(s) for s in sections]

    # 句内词级删冗：{utterance_idx: [(start_ms, end_ms), ...]}
    word_drop = {}
    for tok in a.word_drop.split(","):
        tok = tok.strip()
        if not tok:
            continue
        idx, rng = tok.split(":")
        ws_, we_ = rng.split("-")
        word_drop.setdefault(int(idx), []).append((int(ws_), int(we_)))
    # 逐字稿文字改写：{utterance_idx: 修剪后的整句}
    fix_text = {}
    for tok in a.fix_text.split("|"):
        tok = tok.strip()
        if not tok or "=" not in tok:
            continue
        k, v = tok.split("=", 1)
        fix_text[int(k)] = v.strip()

    # 命名约定（用户定稿 2026-09-14）：音频/文档都带源录音日期
    date_tag = source_date(a.src)
    out = a.out or f"复盘_精剪_{date_tag}.mp3"

    asr = json.loads(Path(a.asr).read_text(encoding="utf-8-sig"))
    utts, all_words = asr["utterances"], asr.get("words", [])
    total = duration(a.src)
    keep = [i for i in range(len(utts)) if i not in set(drop)]
    print(f"源 {total/60:.2f} 分钟 / {len(utts)} 句，删 {len(drop)} 句")

    # ---- 变音区间（毫秒）：整句 --pitch 或 词级 --pitch-words ----
    pitch_spans = []  # [start_ms, end_ms]
    for i in pitch:
        pitch_spans.append([utts[i]["start"], utts[i]["end"]])
    WPAD = 0.06  # 词边界保护
    for term in pitch_words:
        hit = 0
        for i in keep:
            u = utts[i]
            s0, e0 = u["start"], u["end"]
            ws = [w for w in all_words
                  if w.get("text") and s0 <= w["start"] and w["end"] <= e0]
            if not ws:
                continue
            concat = "".join(w["text"] for w in ws)
            pos, starts = 0, []
            for w in ws:
                starts.append(pos)
                pos += len(w["text"])
            at = 0
            while True:
                p = find_term(concat, term, at)
                if p < 0:
                    break
                at = p + len(term)
                wi = next(k for k, st in enumerate(starts) if p < st + len(ws[k]["text"]))
                wj = next(k for k, st in enumerate(starts)
                          if p + len(term) <= st + len(ws[k]["text"]))
                pitch_spans.append([max(s0, ws[wi]["start"] - WPAD * 1000),
                                    min(e0, ws[wj]["end"] + WPAD * 1000)])
                hit += 1
        print(f"变音词「{term}」命中 {hit} 处" + ("（没找到！检查写法）" if not hit else ""))

    # ---- 把保留句切成带变音标记的小片，再按停顿规则合成段 ----
    # piece = (start_s, end_s, is_pitch, utt_index, tight)；
    # tight=True 表示这片紧跟在一段被删掉的词后面，必须强制断开、且回吸要小
    pieces = []
    for i in keep:
        s = max(0.0, utts[i]["start"] / 1000 - PAD)
        e = utts[i]["end"] / 1000 + PAD
        # 先按「句内词级删冗」把该句切成若干保留子区间
        subs, cur, tight = [], s, False
        for ca, cb in sorted(word_drop.get(i, [])):
            ca, cb = max(ca / 1000, s), min(cb / 1000, e)
            if cb <= cur:
                continue
            if ca > cur + 0.02:
                subs.append((cur, ca, tight))
            tight, cur = True, max(cur, cb)
        if e > cur + 0.02:
            subs.append((cur, e, tight))
        if not subs:
            subs = [(s, e, False)]
        # 每个子区间再按变音区间细分
        for sa, sb, tg in subs:
            inside = sorted((a / 1000, b / 1000) for a, b in pitch_spans
                            if b / 1000 > sa and a / 1000 < sb)
            cur2, first = sa, True
            for pa, pb in inside:
                pa, pb = max(pa, sa), min(pb, sb)
                if pa > cur2 + 0.02:
                    pieces.append((cur2, pa, False, i, tg and first))
                pieces.append((max(pa, cur2), pb, True, i, False))
                cur2, first = pb, False
            if sb > cur2 + 0.02:
                pieces.append((cur2, sb, False, i, tg and first))

    drop_set = set(drop)
    segs = [list(pieces[0][:2])]
    seg_pitch = [pieces[0][2]]
    utts_seg = {pieces[0][3]: 0}
    for k, (a2, b2, p2, i, t2) in enumerate(pieces[1:], start=1):
        # 变音段必须独立成段，否则拼接时会把邻居一起变声；
        # 词级删冗后的第一片也必须独立成段，否则会被合并回来
        must_split = p2 != seg_pitch[-1] or t2
        if not must_split and a2 - segs[-1][1] <= KEEP_PAUSE:
            segs[-1][1] = b2
            utts_seg[i] = len(segs) - 1
        else:
            # 坑：回吸不能越进前一个被删句子的尾部，否则会把半个字带回来
            prev_end = max([utts[j]["end"] / 1000 for j in drop_set
                            if j < i and utts[j]["end"] / 1000 <= a2] or [0.0])
            pull = 0.02 if t2 else PULLBACK   # 词级剪口只留 20ms，别把删掉的词吸回来
            segs.append([max(segs[-1][1] + 0.002, a2 - pull, prev_end + 0.06), b2])
            seg_pitch.append(p2)
            utts_seg[i] = len(segs) - 1
    segs[-1][1] = min(segs[-1][1], total)
    _pairs = [(s, p) for s, p in zip(segs, seg_pitch) if s[1] - s[0] > 0.05]
    segs = [x[0] for x in _pairs]
    seg_pitch = [x[1] for x in _pairs]
    if pitch or pitch_spans:
        n_seg = sum(1 for p in seg_pitch if p)
        mode = "哔声遮盖" if a.pitch_mode == "beep" else f"×{a.pitch_factor:.2f} 升调"
        print(f"变音 {n_seg} 段（{mode}），覆盖 "
              f"{sum(e-s for (s,e),p in zip(segs,seg_pitch) if p):.1f}s")

    out_start, acc = [], 0.0
    for s in segs:
        out_start.append(acc)
        acc += s[1] - s[0]
    print(f"保留 {len(segs)} 段，成片 {acc/60:.2f} 分钟（剪掉 {100*(1-acc/total):.1f}%）")

    Path("edl.json").write_text(json.dumps(
        {"v1": {"segments": [[round(s * 1000), round(e * 1000)] for s, e in segs],
                "keep_idx": keep, "drop_idx": drop,
                "word_drop": {str(k): v for k, v in sorted(word_drop.items())},
                # fix_text 必须落进 edl：字幕脚本（make_subs.py）按这里的文本上屏，
                # 否则 --fix-text 只改逐字稿、字幕仍用原始 ASR 文本（2026-10-16 发现）
                "fix_text": {str(k): v for k, v in sorted(fix_text.items())},
                # 字幕遮盖必须使用本次音频实际哔声过的词，避免用户用 --pitch-words
                # 手工覆盖后音频和字幕脱敏范围不一致。
                "pitch_words": pitch_words,
                # keep_text 是「按索引取到的原文快照」：v1_asr.json 一旦被重新转写，
                # 分句会变、索引错位，字幕就会静默串行（2026-10-17 踩到）。
                # make_subs.py 拿它做一致性校验，对不上直接报错。
                "keep_text": {str(i): utts[i]["text"] for i in keep}}},
        ensure_ascii=False, indent=2), encoding="utf-8")

    parts, labels = [], []
    F = a.pitch_factor
    for n, ((s, e), is_p) in enumerate(zip(segs, seg_pitch)):
        dur = e - s
        if is_p and a.pitch_mode == "beep":
            # 哔声遮盖：1kHz 正弦，跟其他段同样的淡入淡出；aformat 对齐声道
            parts.append(f"sine=frequency=1000:sample_rate=48000:duration={dur:.3f},"
                         f"aformat=sample_rates=48000:channel_layouts=stereo,"
                         f"afade=t=in:st=0:d=0.012,"
                         f"afade=t=out:st={dur-0.012:.3f}:d=0.012[a{n}];")
            labels.append(f"[a{n}]")
            continue
        head = f"[0:a]atrim=start={s:.3f}:end={e:.3f},asetpts=PTS-STARTPTS,aresample=48000,"
        if is_p:
            # 变调不变速：asetrate 升调后用 atempo 拉回原速
            head += f"asetrate=48000*{F:.4f},aresample=48000,atempo={1/F:.5f},"
        head += (f"afade=t=in:st=0:d=0.012,"
                 f"afade=t=out:st={dur-0.012:.3f}:d=0.012[a{n}];")
        parts.append(head)
        labels.append(f"[a{n}]")
    chain = DENOISE.get(a.denoise, a.denoise)
    tail = "loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000" if not a.no_loudnorm else "aresample=48000"
    parts.append("".join(labels) + f"concat=n={len(segs)}:v=0:a=1[cat];")
    parts.append("[cat]" + (chain + "," if chain else "") + tail + "[aout]")
    Path("_fc_audio.txt").write_text("\n".join(parts), encoding="utf-8")

    r = None
    if a.no_render:
        print("跳过渲染（--no-render），直接生成逐字稿")
    else:
        r = subprocess.run([FF, "-y", "-i", a.src, "-filter_complex_script", "_fc_audio.txt",
                            "-map", "[aout]", "-c:a", "libmp3lame", "-b:a", "192k", out],
                           capture_output=True, text=True, errors="ignore")
        if r.returncode:
            # 常见坑：成片正被播放器/预览占用 -> Permission denied
            print(r.stderr[-2000:])
            raise SystemExit(1)
        print(f"{out}  {Path(out).stat().st_size/1024/1024:.1f} MB")

    appendix = ["## 已删除内容（供复核）", "", "> 时间戳为**原始录音时间轴**。", ""]
    for i in drop:
        appendix.append(f"- `{mmss(utts[i]['start']/1000)}` {utts[i]['text']}")
    if word_drop:
        appendix += ["", "### 句内词级删冗（重复/口吃）", ""]
        for i in sorted(word_drop):
            spans = "、".join(f"{mmss(s/1000)}-{mmss(e/1000)}" for s, e in sorted(word_drop[i]))
            appendix.append(f"- `{i}` 原句：{utts[i]['text']}")
            appendix.append(f"  - 删掉区间 {spans}")
            if i in fix_text:
                appendix.append(f"  - 修剪后：{fix_text[i]}")

    md_name = f"逐字稿_{date_tag}.md"
    del_name = f"已删除内容_{date_tag}.md"
    if a.plain:
        # 用户定稿格式：只要说话内容，无时间戳、无说话人、无任何标题
        md = Path(out).with_name(md_name)
        md.write_text("\n\n".join(fix_text.get(i, utts[i]["text"]) for i in keep) + "\n",
                      encoding="utf-8")
        Path(out).with_name(del_name).write_text("\n".join(appendix) + "\n", encoding="utf-8")
        print(md)
        return

    lines = ["# 逐字稿", "", f"> 原录音 {total/60:.1f} 分钟 → 成片 {acc/60:.1f} 分钟"
             f"（剪掉 {100*(1-acc/total):.0f}%）。时间戳为**成片时间轴**。", ""]
    groups = sections or [(min(keep), max(keep), "正文")]
    for lo, hi, name in groups:
        idxs = [i for i in keep if lo <= i <= hi]
        if not idxs:
            continue
        lines += [f"## {name}", ""]
        for i in idxs:
            si = utts_seg[i]
            t = out_start[si] + (utts[i]["start"] / 1000 - segs[si][0])
            who = "大人" if i in adult else "孩子"
            lines += [f"**[{mmss(t)}] {who}**：{fix_text.get(i, utts[i]['text'])}", ""]
    lines += ["---", ""] + appendix
    md = Path(out).with_name(md_name)
    md.write_text("\n".join(lines), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
