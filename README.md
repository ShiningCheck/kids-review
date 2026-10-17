# kids-review-editing

小学生每日学习复盘录音精剪：从亲子对话录音里保留围绕学习内容的互动，生成精剪 `mp3`、逐字稿 `md/docx` 和已删除内容清单，并可继续生成封面、字幕和成片 `mp4`。

## 首次配置

完整说明见 [references/setup.md](references/setup.md)。最快路径：

1. 申请火山引擎豆包语音 ASR Key。
2. 安装依赖并生成用户配置：

```powershell
python scripts/setup.py
python scripts/setup.py --check
```

3. 编辑 `%APPDATA%\kids-review-editing\.env`，填入：

```ini
ASR_API_KEY=你的豆包语音 API Key
ASR_BASE_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel
ASR_RESOURCE_ID=volc.seedasr.auc
ASR_TIMEOUT=600
```

4. 编辑 `%APPDATA%\kids-review-editing\profile.json`，填写孩子姓名、学校名等隐私词和编辑偏好。

## 配置位置

| 文件 | 用途 | 是否提交 |
| --- | --- | --- |
| `.env` | ASR Key、接口地址 | 否 |
| `profile.json` | 隐私词、素材目录、编辑偏好 | 否 |
| `.env.example` | `.env` 模板 | 是 |
| `profile.example.json` | `profile.json` 模板 | 是 |

默认配置目录：

- Windows：`%APPDATA%\kids-review-editing`
- macOS：`~/Library/Application Support/kids-review-editing`
- Linux：`$XDG_CONFIG_HOME/kids-review-editing`，未设置时为 `~/.config/kids-review-editing`

可通过 `KIDS_REVIEW_CONFIG_DIR` 覆盖。

## 隐私

这是儿童学习复盘录音工具。使用前请先阅读 [PRIVACY.md](PRIVACY.md)，重点包括：

- 音频会发送到火山引擎豆包语音 ASR 接口。
- `.env` 和 `profile.json` 只放在用户配置目录，不应提交或打包进公开版本。
- 孩子姓名、学校名、同学名和家庭敏感词会默认进入哔声遮盖；同学/家庭敏感句子仍应优先整句删除。
- 视频字幕会同步把隐私词替换成 `哔`，但逐字稿 `md/docx` 默认不遮盖，外发前必须手动检查。

## 依赖

- Python 3.10+，推荐 3.10 到 3.13。
- 音频/文档阶段：`requests`、`python-dotenv`、`imageio-ffmpeg`、`python-docx`。
- 视频阶段：`Pillow`、`numpy`、`scipy`。
- 不需要单独安装 ffmpeg，脚本使用 `imageio-ffmpeg` 提供的可执行文件。
- 需要访问 `openspeech.bytedance.com:443`。

Windows PowerShell 运行脚本前建议设置：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

## 使用

先运行 `setup.py`，使用它输出的 `PY` 和 `S`：

```powershell
PY="<setup.py 输出的 python>"
S="<skill 目录>/scripts"
cd 你的工作目录

& $PY $S/transcribe.py 录音.mp3 -o .
& $PY $S/cut_audio.py 录音.mp3 v1_asr.json --drop 2,3,4 -o 成片.mp3
& $PY $S/verify_audio.py v1_asr.json edl.json verify/v1_asr.json --bad 已删关键词 --good 必须保留关键词

# 需要成片视频时，当天目录里放好 bg_src.jpg 后：
& $PY $S/make_video.py --workdir work/20261016 --date 2026-10-16
```

详细工作流见 [SKILL.md](SKILL.md) 和 [references/review-audio-mode.md](references/review-audio-mode.md)。

## License

[MIT](LICENSE)
