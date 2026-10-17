# ffmpeg / 脚本 硬坑清单（亲子复盘音频分支）

每条都是实际产出过废片或炸过命令的。视频管线（口播/录屏）的坑见姊妹技能
`oral-broadcast-editing` 的 `references/ffmpeg-pitfalls.md`。

## 1. filter_complex 里的逗号被当成滤镜分隔符

- **症状**：`No such filter: '1'`
- **原因**：`select=between(t,1,4)` / `atrim` 表达式里的逗号被 ffmpeg 当成滤镜链分隔
- **修法**：整个表达式用单引号包住 → `select='between(t,1,4)'`

## 2. 滤镜串太长会撑爆 Windows 命令行

- **症状**：`cut_audio.py` 跑 80+ 段时报「命令行太长」或参数被截断
- **原因**：80+ 段 atrim 拼出来的字符串有几 KB，直接塞 `-filter_complex` 超限
- **修法**：**必须走 `-filter_complex_script <file>`**（`cut_audio.py` 已内置）

## 3. `select/aselect` 一次成型 优于 几十个 trim+concat

- 段数多时「几十个 `trim` + `concat`」又慢又容易出错
- 视频用 `select='expr1+expr2+...'` + `setpts=N/FRAME_RATE/TB`；
  音频分支用 `atrim + concat` 但**每段两端必须加 `afade` 12ms** 防爆音

## 4. argparse 的 `-h` 冲突

- **症状**：`ArgumentError: argument -h: conflicting option string: -h`
- **原因**：`-h / --help` 是 argparse 内置，再定义 `-h` 就炸
- **修法**：用长选项或换字母

## 5. Windows 路径 / 无系统 ffmpeg

- ffmpeg 不认 Git Bash 的 `/c/...`，必须写 `C:/...`；或 `cwd=WORK` + 相对文件名
- 一律用 `imageio_ffmpeg.get_ffmpeg_exe()`（内嵌 ffmpeg 7.1）

## 6. docx 中文字体不生效

- python-docx 设字体时，除了 `w:ascii` 和 `w:hAnsi`，**还要设 `w:eastAsia`**，
  否则宋体/黑体不生效
- 逐字稿小节标题色用 `#d91ad9`

## 7. 控制台编码：PowerShell 里先设 `$env:PYTHONIOENCODING="utf-8"`

- 否则脚本 print 到 "✓" 就 `UnicodeEncodeError`（GBK）崩掉，结果文件只写第一行
- 后台长命令约 120s 会被截断，渲染+复检这类 2 分钟以上的活放前台并显式给足超时

## 8. 重剪后必须删掉 verify 目录再复检

- `transcribe.py` 按 `verify/v1_16k.mp3` 是否存在跳过抽音轨；
  旧缓存会把上一版成片又转写一遍，校验结果全是错的（2026-09-15 真实踩过）
