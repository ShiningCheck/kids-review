# 隐私与公开前检查

这个技能处理的是儿童学习复盘录音，属于未成年人个人信息。请只在获得监护人同意的前提下使用，并把它当作**私人编辑工具**，不要把原始录音、逐字稿或未脱敏成片直接公开。

## 数据流

1. `transcribe.py` 在本地用 ffmpeg 抽音轨。
2. 音频会以 base64 形式发送到火山引擎豆包语音 ASR 接口。
3. ASR 结果回到本地，之后的删留、精剪、字幕、成片和复检都在本地完成。
4. `setup.py` 生成的 `.env` 和 `profile.json` 放在用户配置目录，不放在 skill 目录。

因此需要用户自行确认：

- 已了解并接受录音会上传到火山引擎 ASR 服务。
- 录的是自己孩子的复盘，不夹带其他未成年人的可识别对话；确需处理时，应获得对应监护人的同意。
- 不把 `ASR_API_KEY` 写进公开仓库。

## 自动遮盖范围

`profile.json` 的以下字段都会进入默认哔声列表：

```json
{
  "privacy": {
    "child_names": [],
    "english_names": [],
    "school_names": [],
    "classmate_names": [],
    "other_sensitive": []
  }
}
```

音频用 `cut_audio.py --pitch-mode beep` 做 1kHz 哔声遮盖；`make_subs.py` 会用同样的词表把字幕文本替换成 `哔`，避免声音遮了、字幕还露名字。

涉及同学姓名、住址、接送安排等句子的首选做法仍是**整句删除**。自动哔声只是兜底，不能替代人工审查上下文。

## 公开前检查

发布 skill 本身前，确认打包内容里没有：

- `work/` 或任何日期工作目录
- `edl.json`
- `_fc_audio.txt`
- `*.mp3`、`*.wav`、`*.mp4`
- `*.md`、`*.docx`、`*.html` 转写产物
- `.env`
- `profile.json`

发布由 skill 生成的内容前，另做一遍：

1. 检查 `subs2.ass`，确认没有孩子姓名、学校名、同学名和家庭敏感信息。
2. 检查逐字稿 `md/docx`；脚本默认不遮盖文档文本，外发前需要手动打码。
3. 检查 `已删除内容_*.md`，其中保留原始录音时间戳和已删句子，不要一并公开。
4. 重新听成片，确认没有通过变调仍可辨识的姓名、地址或其他敏感上下文。

## 配置与仓库边界

```text
skill 目录（可公开）
├── .env.example
├── profile.example.json
├── scripts/
├── references/
└── PRIVACY.md

用户目录（不可公开）
├── .env
└── profile.json
```

可用 `KIDS_REVIEW_CONFIG_DIR` 覆盖用户配置目录。运行 `python scripts/setup.py --check` 会检查模板、配置、虚拟环境和 ASR Key，但不会回显 Key。
