"""学习复盘录音精剪：按剪辑单精剪音频 + 生成成片台词字幕。

用法：
    python review_cut.py --asr day2_asr.json --src day2.mp3 --edl review_edl.json \
                         -o day2_final.mp3 --srt day2_final.srt --keep day2_keep.json

剪辑单 review_edl.json 格式（人工语义筛选的产物，脚本不替你判断语义）：
{
  "keep": [0, 1, 3, 4],                       # 保留的 utterance 索引
  "trim_head": {"3": "第一节是美术课"},        # 句首碎片：从该标记词开始保留
  "tail_trim": {"8": ["花纹", "花纹"]},        # 句尾碎片：[音频标记词, 字幕标记词]
  "replace":  {"7": [["老师说需", "老师就说要把"]]},   # 仅改字幕文本，不动音频
  "pad_head": 120, "pad_tail": 250,           # 每段首尾留白（ms），防吞字
  "merge_gap": 1200                           # 相邻段间隔小于此值就合并
}

产出：成片 mp3 + 成片 srt（时间码已映射到成片时间轴） + keep.json（供 review_doc / review_page 用）
"""
import argparse
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg


def words_in(words, a, b):
    return [w for w in words if a <= w["start"] < b]


def trim_start(words, u, marker):
    ws = words_in(words, u["start"], u["end"])
    joined = "".join(w["text"] for w in ws)
    ci = joined.find(marker)
    if ci < 0:
        return u["start"], u["text"]
    wi, acc = 0, 0
    for i, w in enumerate(ws):
        acc += len(w["text"])
        if acc > ci:
            wi = i
            break
    text = u["text"][u["text"].find(marker):] if marker in u["text"] else joined[ci:]
    return ws[wi]["start"], text


def trim_end(words, u, marker):
    ws = words_in(words, u["start"], u["end"])
    joined = "".join(w["text"] for w in ws)
    ci = joined.find(marker)
    if ci < 0:
        return u["end"]
    end_char = ci + len(marker) - 1
    acc = 0
    for w in ws:
        acc += len(w["text"])
        if acc > end_char:
            return w["end"]
    return u["end"]


def split_caption(text, st, en):
    """成片台词断行：只在标点后断，且合并过短的半截行。"""
    dur = max(en - st, 0.3)
    units = [c for c in text if c.strip()]
    if not units:
        return []
    per = dur / len(units)
    chunks, cur = [], ""
    for c in text:
        cur += c
        if c in "，。！？；：,.!?;:" or len(cur) >= 16:
            chunks.append(cur)
            cur = ""
    if cur:
        chunks.append(cur)
    fixed = []
    for c in chunks:
        n_ok = len([x for x in c if x.strip()])
        if fixed and n_ok < 5:
            fixed[-1] += c
        else:
            fixed.append(c)
    if len(fixed) > 1 and len([x for x in fixed[0] if x.strip()]) < 5:
        fixed[1] = fixed[0] + fixed[1]
        fixed.pop(0)
    out, t = [], st
    for c in fixed:
        k = len([x for x in c if x.strip()])
        out.append((t, t + per * k, c.strip()))
        t += per * k
    return out


def fmt_srt(sec):
    h = int(sec // 3600)
    m = int(sec % 3600 // 60)
    return f"{h:02d}:{m:02d}:{sec%60:06.3f}".replace(".", ",")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asr", required=True)
    ap.add_argument("--src", required=True, help="原始音频（或视频，ffmpeg 会自己取音轨）")
    ap.add_argument("--edl", required=True)
    ap.add_argument("-o", "--out", required=True, help="成片 mp3")
    ap.add_argument("--srt", default=None, help="成片 srt")
    ap.add_argument("--keep", default=None, help="keep.json（给 review_doc / review_page）")
    ap.add_argument("--bitrate", default="128k")
    a = ap.parse_args()

    data = json.loads(Path(a.asr).read_text(encoding="utf-8-sig"))
    utts, words = data["utterances"], data["words"]
    edl = json.loads(Path(a.edl).read_text(encoding="utf-8-sig"))
    KEEP = edl["keep"]
    TRIM_HEAD = {int(k): v for k, v in edl.get("trim_head", {}).items()}
    TAIL_TRIM = {int(k): v for k, v in edl.get("tail_trim", {}).items()}
    REPLACE = {int(k): v for k, v in edl.get("replace", {}).items()}
    pad_h = edl.get("pad_head", 120)
    pad_t = edl.get("pad_tail", 250)
    merge_gap = edl.get("merge_gap", 1200)

    segs, captions = [], []
    for i in KEEP:
        u = utts[i]
        if i in TRIM_HEAD:
            s, text = trim_start(words, u, TRIM_HEAD[i])
        else:
            s, text = u["start"], u["text"]
        e = trim_end(words, u, TAIL_TRIM[i][0]) if i in TAIL_TRIM else u["end"]
        for old, new in REPLACE.get(i, []):
            text = text.replace(old, new)
        if i in TAIL_TRIM:
            p = text.find(TAIL_TRIM[i][1])
            if p >= 0:
                text = text[:p + len(TAIL_TRIM[i][1])]
        segs.append([max(0, s - pad_h), e + pad_t])
        captions.append((s, e, text))

    merged = [segs[0]]
    for s in segs[1:]:
        if s[0] - merged[-1][1] < merge_gap:
            merged[-1][1] = s[1]
        else:
            merged.append(s)

    total = sum(e - s for s, e in merged) / 1000
    orig = data["duration_ms"] / 1000
    print(f"保留 {len(KEEP)} 句 -> {len(merged)} 段，{total:.0f}s"
          f"（原 {orig/60:.1f} 分钟，压缩 {100-total/orig*100:.0f}%）")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    n = len(merged)
    parts = [f"[0:a]asplit={n}" + "".join(f"[a{i}]" for i in range(n)) + ";"]
    streams = []
    for i, (s, e) in enumerate(merged):
        parts.append(f"[a{i}]atrim=start={s/1000:.3f}:end={e/1000:.3f},"
                     f"asetpts=PTS-STARTPTS[sa{i}];")
        streams.append(f"[sa{i}]")
    parts.append("".join(streams) + f"concat=n={n}:v=0:a=1[oa]")
    r = subprocess.run([ff, "-y", "-i", str(a.src), "-filter_complex", "".join(parts),
                        "-map", "[oa]", "-c:a", "libmp3lame", "-b:a", a.bitrate, a.out],
                       capture_output=True, text=True, errors="ignore")
    if r.returncode != 0:
        print(r.stderr[-1500:])
        raise SystemExit(1)
    print(f"成片: {a.out}  {Path(a.out).stat().st_size/1024/1024:.1f} MB  {total:.0f}s")

    # 原片时间 → 成片时间
    off, mapping = 0.0, []
    for s, e in merged:
        mapping.append((s / 1000, e / 1000, off))
        off += (e - s) / 1000

    def map_ms(t_ms):
        t = t_ms / 1000
        for s, e, o in mapping:
            if s <= t < e:
                return o + (t - s)
        for s, e, o in mapping:
            if abs(t - e) < 0.05:
                return o + (e - s)
        return None

    if a.srt:
        lines, idx, prev = [], 1, None
        for st_ms, en_ms, text in captions:
            for (s, e, c) in split_caption(text, st_ms / 1000, en_ms / 1000):
                ns, ne = map_ms(s * 1000), map_ms(e * 1000)
                if ns is None:
                    continue
                ne = ne if ne is not None else ns + 0.5
                if prev is not None and ns < prev + 0.08:
                    ns = prev + 0.08
                if ne <= ns:
                    ne = ns + 0.3
                lines.append(f"{idx}\n{fmt_srt(ns)} --> {fmt_srt(ne)}\n{c}\n")
                idx += 1
                prev = ne
        Path(a.srt).write_text("\n".join(lines), encoding="utf-8")
        print(f"字幕: {a.srt}  {idx-1} 条")

    if a.keep:
        Path(a.keep).write_text(json.dumps({
            "keep": KEEP, "segments": merged,
            "captions": [{"idx": KEEP[j], "start": s, "end": e, "text": t}
                         for j, (s, e, t) in enumerate(captions)],
        }, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"剪辑记录: {a.keep}")


if __name__ == "__main__":
    main()
