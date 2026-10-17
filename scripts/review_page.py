"""复盘录音精剪复核页：成片台词 + 已删内容分组勾选恢复。

用法：
    python review_page.py --keep day2_keep.json --asr day2_asr.json \
        --audio day2_final.mp3 --srt day2_final.srt \
        --groups groups.json --sections sections.json \
        --title "9/10 亲子复盘录音精剪 · 复核" -o review.html

groups.json 格式（已删句子的归类，**逐组人工看过才填**）：
{
  "生活流水账": {"desc": "吃饭/纸巾/放学等车——与学习无关", "idx": [10, 11]},
  "疑似可恢复": {"desc": "与学习沾边但当前被删掉了，建议逐句看一眼", "idx": [2, 9]}
}
sections.json 复用于成片台词里的小节分隔标记（同 review_doc.py）。

页面底部按钮生成「恢复索引：3,7,12」，把它加回剪辑单的 keep 再跑一遍 review_cut.py。
"""
import argparse
import json
from pathlib import Path


def mmss(s):
    return f"{int(s//60)}:{s%60:05.2f}"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", required=True)
    ap.add_argument("--asr", required=True)
    ap.add_argument("-o", "--out", default="review.html")
    ap.add_argument("--audio", default=None, help="成片音频（页面内嵌播放器）")
    ap.add_argument("--srt", default=None)
    ap.add_argument("--groups", default=None)
    ap.add_argument("--sections", default=None)
    ap.add_argument("--title", default="学习复盘录音精剪 · 复核")
    ap.add_argument("--subtitle", default="保留「孩子学习情况 + 学习内容描述 + 亲子互动」")
    a = ap.parse_args()

    data = json.loads(Path(a.asr).read_text(encoding="utf-8-sig"))
    utts = data["utterances"]
    keep = json.loads(Path(a.keep).read_text(encoding="utf-8-sig"))
    KEEP = set(keep["keep"])
    segments = keep["segments"]
    orig = data["duration_ms"] / 1000
    final_s = sum(b - s for s, b in segments) / 1000

    off, mapping = 0.0, []
    for s, e in segments:
        mapping.append((s / 1000, e / 1000, off))
        off += (e - s) / 1000

    def to_final(t_ms):
        t = t_ms / 1000
        for s, e, o in mapping:
            if s <= t < e:
                return o + (t - s)
        return None

    CAP = {c["idx"]: c for c in keep["captions"]}
    SUBJECT = {}
    if a.sections:
        for name, idxs in json.loads(Path(a.sections).read_text(encoding="utf-8-sig")):
            if idxs:
                SUBJECT[idxs[0]] = name

    kept_rows = ""
    for i in sorted(KEEP):
        c = CAP[i]
        if i in SUBJECT:
            kept_rows += f'<div class="sec">▎{SUBJECT[i]}</div>'
        ft = to_final(c["start"])
        kept_rows += (f'<div class="row kept"><span class="idx">{i}</span>'
                      f'<span class="tc">{mmss(ft) if ft is not None else "--:--"}</span>'
                      f'<span class="tx">{c["text"]}</span></div>')

    groups_raw = json.loads(Path(a.groups).read_text(encoding="utf-8-sig")) if a.groups else {}
    order = list(groups_raw.keys())
    buckets = {g: [] for g in order}
    buckets["未归类"] = []
    owner = {}
    for g, spec in groups_raw.items():
        for i in spec.get("idx", []):
            owner[i] = g
    for i, u in enumerate(utts):
        if i in KEEP:
            continue
        buckets[owner.get(i, "未归类")].append((i, mmss(u["start"] / 1000), u["text"]))
    if "未归类" not in order:
        order.append("未归类")

    gblocks = ""
    for g in order:
        rows = buckets.get(g, [])
        if not rows:
            continue
        desc = groups_raw.get(g, {}).get("desc", "")
        items = "".join(
            f'<label class="row del"><input type="checkbox" value="{i}">'
            f'<span class="idx">{i}</span><span class="tc">{t}</span>'
            f'<span class="tx">{x}</span></label>' for i, t, x in rows)
        gblocks += (f'<div class="grp"><div class="gh"><b>{g}</b>'
                    f'<span class="cnt">{len(rows)} 句</span></div>'
                    f'<div class="gd">{desc}</div>{items}</div>')

    n_srt = 0
    if a.srt and Path(a.srt).exists():
        n_srt = Path(a.srt).read_text(encoding="utf-8-sig").count("\n\n") + 1

    audio = (f'<div class="card"><h2>成片音轨</h2>'
             f'<audio controls src="{Path(a.audio).name}"></audio></div>') if a.audio else ""

    html = f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>{a.title}</title><style>
*{{box-sizing:border-box}}
body{{margin:0;padding:28px;background:#f6f7f9;color:#1d2129;
font:14px/1.6 -apple-system,"PingFang SC","Microsoft YaHei",sans-serif}}
.wrap{{max-width:1080px;margin:0 auto}}
h1{{font-size:20px;margin:0 0 4px}}
.sub{{color:#86909c;font-size:13px;margin-bottom:18px}}
.stats{{display:flex;gap:10px;flex-wrap:wrap;margin-bottom:18px}}
.stat{{background:#fff;border:1px solid #e5e6eb;border-radius:8px;padding:10px 16px}}
.stat b{{display:block;font-size:19px}}
.stat span{{font-size:12px;color:#86909c}}
.card{{background:#fff;border:1px solid #e5e6eb;border-radius:10px;padding:18px;margin-bottom:16px}}
.card h2{{font-size:15px;margin:0 0 12px}}
audio{{width:100%}}
.row{{display:flex;gap:10px;align-items:flex-start;padding:6px 8px;border-radius:6px}}
.row:hover{{background:#f2f3f5}}
.idx{{width:34px;color:#c9cdd4;font-size:12px;text-align:right;flex:none;padding-top:2px}}
.tc{{width:56px;color:#d91ad9;font-size:12px;font-family:ui-monospace,Consolas,monospace;flex:none;padding-top:2px}}
.tx{{flex:1}}
.del{{cursor:pointer}}.del .tx{{color:#86909c}}.del input{{margin-top:5px;flex:none}}
.grp{{margin-bottom:14px}}
.gh{{display:flex;align-items:center;gap:8px;margin:14px 0 2px}}
.gh b{{font-size:14px}}
.cnt{{background:#f2f3f5;border-radius:10px;padding:1px 9px;font-size:12px;color:#86909c}}
.gd{{color:#86909c;font-size:12px;margin-bottom:4px}}
.bar{{position:sticky;bottom:0;background:#fff;border:1px solid #e5e6eb;border-radius:10px;
padding:12px 16px;display:flex;gap:12px;align-items:center}}
button{{background:#d91ad9;color:#fff;border:0;border-radius:6px;padding:8px 18px;font-size:13px;cursor:pointer}}
button.ghost{{background:#fff;color:#1d2129;border:1px solid #e5e6eb}}
#out{{flex:1;font-family:ui-monospace,Consolas,monospace;font-size:12px;color:#d91ad9}}
.sec{{font-size:13px;color:#86909c;margin:16px 0 4px;font-weight:600}}
</style></head><body><div class="wrap">
<h1>{a.title}</h1>
<div class="sub">{a.subtitle}</div>
<div class="stats">
<div class="stat"><b>{mmss(final_s)}</b><span>成片时长</span></div>
<div class="stat"><b>{mmss(orig)}</b><span>原始时长</span></div>
<div class="stat"><b>-{round(100-final_s/orig*100)}%</b><span>压缩比</span></div>
<div class="stat"><b>{len(KEEP)}</b><span>保留句数</span></div>
<div class="stat"><b>{len(utts)-len(KEEP)}</b><span>删除句数</span></div>
<div class="stat"><b>{n_srt}</b><span>字幕条数</span></div>
</div>
{audio}
<div class="card"><h2>成片台词（{len(KEEP)} 句，含课程分段）</h2>{kept_rows}</div>
<div class="card"><h2>已删除内容（勾选＝要恢复）</h2>{gblocks}</div>
</div>
<div class="bar"><button onclick="gen()">生成恢复清单</button>
<button class="ghost" onclick="selAll(true)">全选</button>
<button class="ghost" onclick="selAll(false)">清空</button>
<div id="out"></div></div>
<script>
function selAll(v){{document.querySelectorAll('.del input').forEach(function(c){{c.checked=v}})}}
function gen(){{var a=[];document.querySelectorAll('.del input:checked').forEach(function(c){{a.push(+c.value)}});
document.getElementById('out').textContent=a.length?('恢复索引：'+a.join(',')):'（没有勾选任何句子）';}}
</script></body></html>"""

    Path(a.out).write_text(html, encoding="utf-8")
    print(f"{a.out}  {Path(a.out).stat().st_size/1024:.0f} KB  "
          f"保留{len(KEEP)} 删除{len(utts)-len(KEEP)}")
    for g in order:
        if buckets.get(g):
            print(f"  {g}: {len(buckets[g])}")


if __name__ == "__main__":
    main()
