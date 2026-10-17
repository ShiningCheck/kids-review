# -*- coding: utf-8 -*-
"""步骤 4.5（音频版）：对成片重新 ASR，校验「该删的删干净、该留的没切坏」

    python cut_audio.py ...            # 先出成片
    python transcribe.py 成片.mp3 -o verify
    python verify_audio.py v1_asr.json edl.json verify/v1_asr.json \
        --bad 刷牙,炸鸡腿 --good 金木水火土,七步洗手法

音频没有字幕可比对，所以改用「关键词有/无 + 文本相似度」三连检。
这步不能省：ffmpeg 剪错了不报错，只有重新听（或重新 ASR）才发现。
"""
import argparse, difflib, json
from pathlib import Path


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("src_asr")
    ap.add_argument("edl")
    ap.add_argument("out_asr")
    ap.add_argument("--bad", default="", help="已删内容的独有望词，逗号分隔")
    ap.add_argument("--good", default="", help="必须保留的关键词，逗号分隔")
    a = ap.parse_args()

    src = json.loads(Path(a.src_asr).read_text(encoding="utf-8-sig"))["utterances"]
    edl = json.loads(Path(a.edl).read_text(encoding="utf-8-sig"))
    out = json.loads(Path(a.out_asr).read_text(encoding="utf-8-sig"))
    keep = edl["v1"]["keep_idx"]
    got = out.get("text", "")
    print(f"成片 ASR {len(out['utterances'])} 句 / {len(got)} 字")

    bad = [w for w in a.bad.split(",") if w.strip()]
    hit = [w for w in bad if w in got]
    print("① 已删内容残留：", "、".join(hit) if hit else "无 ✓")

    good = [w for w in a.good.split(",") if w.strip()]
    miss = [w for w in good if w not in got]
    print("② 关键内容缺失：", "、".join(miss) if miss else "无 ✓")

    exp = "".join(c for c in "".join(src[i]["text"] for i in sorted(keep)) if c.strip())
    g2 = "".join(c for c in got if c.strip())
    r = difflib.SequenceMatcher(None, exp, g2).quick_ratio()
    print(f"③ 文本相似度 {r:.3f}（预期 {len(exp)} 字 / 成片 {len(g2)} 字）")

    print(f"④ 首句 期望「{src[min(keep)]['text'][:30]}」"
          f" 实际「{out['utterances'][0]['text'][:30]}」")
    ok = not hit and not miss and r > 0.9
    print("\n结论：", "通过 ✓" if ok else "需人工复核 ✗")


if __name__ == "__main__":
    main()
