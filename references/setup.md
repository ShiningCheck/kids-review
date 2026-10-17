# 首次配置说明

公开与隐私边界见 [../PRIVACY.md](../PRIVACY.md)。以下配置用于本机使用。

## 1. 申请火山引擎 ASR Key

公开版只使用火山引擎豆包语音转写，因此必须先有自己的 ASR Key。

1. 注册并完成火山引擎实名认证：[火山引擎控制台](https://console.volcengine.com/)。
2. 进入[豆包语音控制台](https://console.volcengine.com/speech/new/experience/asr)。
3. 在“开通管理”中开通“录音文件识别大模型-极速版”。
4. 在“API Key 管理”中创建 API Key，并保存该值。

注意事项：

- 必须使用“豆包语音控制台”签发的 Key。
- 火山方舟/大模型平台的 API Key 不通用。
- 服务未开通时，即使 Key 有效，请求也可能被拒绝。
- 接口文档：[录音文件识别标准版 HTTP](https://docs.volcengine.com/docs/6561/1354868?lang=zh)。
- 计费按实际转写音频时长计算，具体价格与开通状态以控制台为准。

## 2. 安装依赖

在 skill 根目录运行：

```powershell
python scripts/setup.py
```

该脚本会：

- 创建用户配置目录。
- 从 `.env.example` 生成 `.env`。
- 从 `profile.example.json` 生成 `profile.json`。
- 创建独立 venv 并安装 `requirements.txt`。
- 输出后续命令需要的 `PY` 和 `S`。

只检查不安装：

```powershell
python scripts/setup.py --check
```

自定义配置目录或 venv：

```powershell
python scripts/setup.py --config-dir D:/kids-review-config --venv-dir D:/kids-review-venv
```

Python 依赖：

```text
requests
python-dotenv
imageio-ffmpeg
python-docx
Pillow
numpy
scipy
```

不要求单独安装 ffmpeg。脚本使用 `imageio_ffmpeg.get_ffmpeg_exe()`。

Windows PowerShell 运行脚本前设置：

```powershell
$env:PYTHONIOENCODING="utf-8"
```

否则输出勾号等 Unicode 字符时可能因 GBK 编码报错。

## 3. `.env` 配置

默认位置：`<配置目录>/.env`。

| 变量 | 必填 | 说明 | 默认值 |
| --- | --- | --- | --- |
| `ASR_API_KEY` | 是 | 豆包语音控制台 API Key | 无 |
| `ASR_BASE_URL` | 否 | 豆包录音文件识别 HTTP 根地址 | `https://openspeech.bytedance.com/api/v3/auc/bigmodel` |
| `ASR_RESOURCE_ID` | 否 | 录音文件识别模型 2.0 资源 ID | `volc.seedasr.auc` |
| `ASR_TIMEOUT` | 否 | 单次 HTTP 超时秒数 | `600` |

示例：

```ini
ASR_API_KEY=你的 Key
ASR_BASE_URL=https://openspeech.bytedance.com/api/v3/auc/bigmodel
ASR_RESOURCE_ID=volc.seedasr.auc
ASR_TIMEOUT=600
```

`.env` 不应提交到公开仓库。

## 4. `profile.json` 配置

默认位置：`<配置目录>/profile.json`。

```json
{
  "privacy": {
    "child_names": ["孩子中文名", "同音写法"],
    "english_names": ["英文名", "小名"],
    "school_names": ["学校全名", "学校简称"],
    "classmate_names": ["同学姓名"],
    "other_sensitive": ["托管班名", "住址关键词"]
  },
  "media": {
    "source_dirs": ["D:/录音素材"],
    "output_root": "",
    "organize_by_date": true
  },
  "editing": {
    "plain_transcript": true,
    "privacy_mode": "beep",
    "pitch_factor": 1.3,
    "denoise": "light",
    "loudnorm": true,
    "docx_font": "微软雅黑",
    "docx_body_pt": 11
  },
  "video": {
    "title_line1": "我的一年级",
    "title_line2": "第一学期",
    "intro_seconds": 6.0,
    "resolution": "1440x1080",
    "crf": "20",
    "cover_font": "",
    "subtitle_font": "YouZiKuLongCang",
    "subtitle_font_size": 74,
    "subtitle_outline": 6,
    "subtitle_shadow": 2,
    "subtitle_margin_v": 46,
    "subtitle_max_chars": 15
  }
}
```

字段说明：

- `child_names`、`english_names`、`school_names`、`classmate_names`、`other_sensitive`
  都会自动作为 `--pitch-words` 的默认值。
- 同学姓名和家庭敏感信息仍应优先整句删除；自动哔声是删不掉时的兜底。
- `source_dirs` 是默认素材搜索目录，留空则从当前工作目录开始。
- `output_root` 留空时输出到当前工作目录。
- `privacy_mode` 可选 `beep` 或 `pitch`；`beep` 是彻底遮盖，`pitch` 是变调。
- `denoise` 可选 `off`、`light`、`mid`、`strong`。
- `docx_font` 和 `docx_body_pt` 用于逐字稿 Word 输出。
- `video.cover_font` 可填马善政体字体文件的绝对路径；留空时自动在 skill 的 `assets/fonts/`、用户字体目录和 Windows 字体目录中查找。
- `video.subtitle_font` 是 ASS 字幕字体名，要求系统中已安装对应字体。
- `video.title_line1/title_line2`、`intro_seconds`、`resolution`、`crf` 是成片视频的默认值，仍可被命令行参数覆盖。

每次录音才决定的参数不写入 profile：`--drop`、`--adult`、`--bad`、`--good`、`--sections`、`--groups`。

## 5. 公开前检查

只公开 skill 本身时，打包内容不能包含 `work/`、`edl.json`、`_fc_audio.txt`、`.env`、
`profile.json`、音频/视频/转写产物和 `__pycache__`。完整清单见 [../PRIVACY.md](../PRIVACY.md)。

公开由 skill 生成的成片前，至少检查 `subs2.ass`、逐字稿和 `已删除内容_*.md`，并重新听一遍成片。

## 6. 常见问题

| 现象 | 处理 |
| --- | --- |
| 缺少 `ASR_API_KEY` | 编辑 `.env` 或设置环境变量后重跑 `setup.py --check` |
| HTTP 401 / 403 | 检查是否使用豆包语音控制台 Key，以及服务是否已开通 |
| 请求被拒但 Key 正确 | 确认“开通管理”里已开通录音文件识别大模型-极速版 |
| `ModuleNotFoundError` | 使用 `setup.py` 输出的 venv Python，而不是系统 Python |
| PowerShell 报 Unicode 编码错误 | 先设置 `$env:PYTHONIOENCODING="utf-8"` |
