# -*- coding: utf-8 -*-
"""《我的一年级》封面：当天水彩画做底 + 上期同款「红田字格块 + 米黄手写体」标题。

版式（沿用 2026-10-07 定稿的参考图）：
  - 每字一个红方块，微旋转，田字格虚线，米黄粗楷体（柔和投影，不用描边）
  - 三行整体各自倾斜一点
  - 三行：我的一年级 / 第一学期 / 10.16 周五

用法：
    # 横版（视频封面 + 正文背景），会顺带产出 bg_1440.png 供 build_video 用
    python make_cover.py --workdir <当天目录> --date 2026-10-16

    # 竖版（发布用，3:4 安全区），必须 --no-bg，否则会把 bg_1440.png 覆写成竖版
    python make_cover.py --workdir <当天目录> --date 2026-10-16 --size 1080x1920 \
        --out 封面_竖版.png --no-bg

⚠️ bg_1440.png 是 build_video 用的正文背景，尺寸必须与视频一致（1440x1080）。
   竖版封面如果也写 bg_1440.png，渲染会直接崩（2026-10-12 / 10-16 各踩一次）。
   所以出竖版时一律 `--no-bg`，或者干脆放在渲染之后出。
"""
import argparse
import random
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402

from config import load_profile  # noqa: E402

PROFILE = load_profile()
VIDEO = PROFILE.get("video", {})
SKILL_ROOT = Path(__file__).resolve().parents[1]

BLOCK_RED = (166, 44, 36, 255)        # 主块暗红
BLOCK_RED_DK = (120, 28, 22, 255)     # 块阴影
GRID = (242, 217, 163, 80)            # 田字格虚线（米色半透明）
INK = (243, 220, 168, 255)            # 字色米黄
INK_SHADOW = (55, 12, 8, 215)         # 字投影

WEEKDAYS = "一二三四五六日"


def font_candidates() -> list[Path]:
    configured = str(VIDEO.get("cover_font", "")).strip()
    candidates = [Path(configured).expanduser()] if configured else []
    candidates += [
        SKILL_ROOT / "assets" / "fonts" / "MaShanZheng-Regular.ttf",
        Path.home() / "AppData/Local/Microsoft/Windows/Fonts/MaShanZheng-Regular.ttf",
        Path("C:/Windows/Fonts/MaShanZheng-Regular.ttf"),
    ]
    return candidates


def find_font() -> Path:
    candidates = font_candidates()
    for p in candidates:
        if p.exists():
            return p
    raise SystemExit(f"找不到马善政体，试过：{[str(p) for p in candidates]}")


def bg_image(src: Path, W: int, H: int) -> Image.Image:
    """先削掉纸张白边，再按目标画布比例居中裁切后铺满。"""
    import numpy as np
    im = Image.open(src).convert("RGB")
    w, h = im.size
    m = int(min(w, h) * 0.06)
    im = im.crop((m, m, w - m, h - m))
    a = np.asarray(im.convert("L")).astype("int16")
    mask = a < 235
    if mask.any():
        rows = np.where(mask.any(axis=1))[0]
        cols = np.where(mask.any(axis=0))[0]
        im = im.crop((int(cols[0]), int(rows[0]),
                      int(cols[-1]) + 1, int(rows[-1]) + 1))
    print("   背景去白边 ->", im.size)
    w, h = im.size
    tw = int(h * W / H)
    if tw <= w:
        x0 = (w - tw) // 2
        im = im.crop((x0, 0, x0 + tw, h))
    else:
        th = int(w * H / W)
        y0 = (h - th) // 2
        im = im.crop((0, y0, w, y0 + th))
    return im.resize((W, H), Image.LANCZOS)


def dashed_line(d, p0, p1, fill, width=3, dash=12, gap=9):
    import math
    x0, y0 = p0
    x1, y1 = p1
    dist = math.hypot(x1 - x0, y1 - y0)
    if dist == 0:
        return
    n = int(dist // (dash + gap)) + 1
    ux, uy = (x1 - x0) / dist, (y1 - y0) / dist
    for i in range(n):
        s = i * (dash + gap)
        e = min(s + dash, dist)
        if s >= dist:
            break
        d.line([(x0 + ux * s, y0 + uy * s), (x0 + ux * e, y0 + uy * e)],
               fill=fill, width=width)


def char_tile(ch: str, size: int, font_path: Path) -> Image.Image:
    """一个字的红块 + 田字格 + 米黄字（柔和投影）。"""
    pad = int(size * 0.06)
    s = size + pad * 2
    tile = Image.new("RGBA", (s, s), (0, 0, 0, 0))
    d = ImageDraw.Draw(tile)
    off = int(size * 0.055)
    d.rectangle([pad + off, pad + off, pad + size + off, pad + size + off],
                fill=BLOCK_RED_DK)
    d.rectangle([pad, pad, pad + size, pad + size], fill=BLOCK_RED)
    m = size // 2
    c = pad
    for p0, p1 in [((c + m, c), (c + m, c + size)), ((c, c + m), (c + size, c + m)),
                   ((c, c), (c + size, c + size)), ((c + size, c), (c, c + size))]:
        dashed_line(d, p0, p1, GRID, width=3)

    dot = ch == "."
    fsize = int(size * (0.72 if dot else 0.84))
    f = ImageFont.truetype(str(font_path), fsize)
    bbox = d.textbbox((0, 0), ch, font=f)
    fw, fh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    x = pad + (size - fw) // 2 - bbox[0]
    y = (pad + size - int(size * 0.16) - fh - bbox[1]) if dot \
        else (pad + (size - fh) // 2 - bbox[1] + int(size * 0.02))

    sh = max(3, int(size * 0.06))
    blur = max(2, int(size * 0.03))
    shadow = Image.new("RGBA", tile.size, (0, 0, 0, 0))
    ImageDraw.Draw(shadow).text((x, y), ch, font=f, fill=INK_SHADOW)
    shadow = shadow.filter(ImageFilter.GaussianBlur(blur))
    tile.alpha_composite(shadow, (sh, sh))
    d.text((x, y), ch, font=f, fill=INK)
    return tile


def paste_line(base: Image.Image, text: str, cy: int, size: int,
               angle: float, dx: int, W: int, font_path: Path):
    """一行字块：先拼成整行，再整体旋转 angle 度，最后贴到 base 的 cy 处。"""
    tiles = []
    for ch in text:
        if ch == " ":
            tiles.append(None)          # 空格 = 一个额外间距
            continue
        s = int(size * (0.36 if ch == "." else 1.0))
        ang = random.uniform(-2.6, 2.6)
        tiles.append(char_tile(ch, s, font_path).rotate(ang, expand=True,
                                                        resample=Image.BICUBIC))
    gap = int(size * 0.045)
    space = int(size * 0.30)
    total = sum(t.width if t else space for t in tiles) + gap * max(0, len(tiles) - 1)
    hmax = max((t.height for t in tiles if t), default=int(size * 1.1))
    row = Image.new("RGBA", (total + 80, hmax + 80), (0, 0, 0, 0))
    x = 40
    for t in tiles:
        if t is None:
            x += space
            continue
        row.alpha_composite(t, (x, 40 + (hmax - t.height) // 2))
        x += t.width + gap
    row = row.rotate(angle, expand=True, resample=Image.BICUBIC)
    base.alpha_composite(row, ((W - row.width) // 2 + dx, cy - row.height // 2))


def auto_line3(date: str) -> str:
    """2026-10-16 -> '10.16 周五'"""
    import datetime as dt
    d = dt.date.fromisoformat(date)
    return f"{d.month}.{d.day} 周{WEEKDAYS[d.weekday()]}"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--workdir", default=".", help="当天产物目录（放 bg_src.jpg 等）")
    ap.add_argument("--bg", default="", help="水彩画路径，默认 <workdir>/bg_src.jpg")
    ap.add_argument("--size", default=VIDEO.get("resolution", "1440x1080"),
                    help="画布尺寸，如 1440x1080 / 1080x1920")
    ap.add_argument("--out", default="", help="封面输出名，默认 封面_<日期>.png")
    ap.add_argument("--date", required=True, help="播出日期 YYYY-MM-DD，用于第三行")
    ap.add_argument("--line1", default=VIDEO.get("title_line1", "我的一年级"))
    ap.add_argument("--line2", default=VIDEO.get("title_line2", "第一学期"))
    ap.add_argument("--line3", default="", help="留空则按 --date 自动生成「10.16 周五」")
    ap.add_argument("--font", default="", help="封面字体文件路径；留空用 profile 或自动查找")
    ap.add_argument("--seed", type=int, default=0, help="随机种子，默认取日期，保证同一天可复现")
    ap.add_argument("--bg-out", default="bg_1440.png",
                    help="正文背景输出名（build_video 用），传空串则不产出")
    ap.add_argument("--no-bg", action="store_true",
                    help="不产出正文背景（出竖版封面时必须加，否则覆写 bg_1440.png 会让渲染崩）")
    a = ap.parse_args()
    if a.no_bg:
        a.bg_out = ""

    workdir = Path(a.workdir).resolve()
    W, H = (int(x) for x in a.size.lower().split("x"))
    bg_src = Path(a.bg) if a.bg else workdir / "bg_src.jpg"
    if not bg_src.exists():
        raise SystemExit(f"找不到背景图：{bg_src}")
    out = workdir / (a.out or f"封面_{a.date.replace('-', '年', 1).replace('-', '月', 1)}日.png")
    line3 = a.line3 or auto_line3(a.date)
    random.seed(a.seed or int(a.date.replace("-", "")))
    font_path = Path(a.font).expanduser() if a.font else find_font()
    if a.font and not font_path.exists():
        raise SystemExit(f"找不到封面字体：{font_path}")

    base = bg_image(bg_src, W, H).convert("RGBA")
    veil = Image.new("RGBA", (W, H), (255, 250, 240, 36))
    base.alpha_composite(veil)

    k = W / 1440.0
    size = int(178 * k)
    for text, cy, ang, dx, sz in (
        (a.line1, int(0.20 * H), -2.6, int(-38 * k), size),
        (a.line2, int(0.41 * H), -1.8, int(58 * k), size),
        (line3, int(0.74 * H), -2.2, 0, int(168 * k)),
    ):
        if text:
            paste_line(base, text, cy, sz, ang, dx, W, font_path)

    base.convert("RGB").save(out)
    print(f"封面 {W}x{H} -> {out}")

    if a.bg_out:
        bg = bg_image(bg_src, W, H)
        bg.save(workdir / a.bg_out)
        print(f"正文背景 -> {a.bg_out}（{W}x{H}）")
    else:
        print("（--no-bg / bg-out 为空：未写正文背景）")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
