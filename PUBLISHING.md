# WorkBuddy 技能市场发布清单

这个文件用于把 `kids-review-editing` 从本地技能包提交到 WorkBuddy 开放平台。公开包已按隐私边界生成，不包含真实录音、转写产物、用户 `.env` 或 `profile.json`。

## 待上传文件

| 用途 | 文件 |
| --- | --- |
| Skill 包 | `C:\Users\Danmiao\.workbuddy\skills\kids-review-editing.zip` |
| 市场头像 | `C:\Users\Danmiao\.workbuddy\skills\kids-review-editing\assets\icon.png` |

## 平台填写信息

| 字段 | 建议值 |
| --- | --- |
| 展示名称 | `儿童学习复盘录音精剪` |
| 英文名称 | `Kids Review Audio Editing` |
| 分类 | 优先选择 `效率` / `Productivity`；若平台没有，再选最接近的教育或音视频处理类目 |
| 版本 | `0.3.0` |
| 作者 | `查查` |
| License | `MIT` |

简介建议保留这句：

```text
儿童每日学习复盘录音精剪：转写亲子对话、删冗余、隐私哔声，并生成逐字稿、封面、字幕和成片视频。需要用户自己的火山引擎豆包语音 ASR_API_KEY。
```

英文简介：

```text
Edit children's daily learning review recordings: transcribe parent-child conversations, remove redundant content, beep private terms, and produce transcripts, covers, subtitles, and MP4 videos. Requires the user's own Volcano Engine ASR_API_KEY.
```

## 操作顺序

1. 打开并确认已登录认证的开发后台：<https://open.workbuddy.cn/dashboard>。
2. 进入左侧或首页的 `技能` 入口，选择 `添加技能` / `创建技能` / `上传技能`。
3. 上传 `kids-review-editing.zip`。
4. 等平台解析 `SKILL.md`；如果提示 YAML 或结构错误，按平台提示修正后重新上传。
5. 平台自动读取大部分字段后，补选分类、服务类目并上传 `assets/icon.png`。
6. 在简介或说明里注明需要用户自备 `ASR_API_KEY`，并链接或保留 [PRIVACY.md](PRIVACY.md)。
7. 提交审核。平台通常会执行安全扫描、AI 审核和人工抽检，审核通过后才出现在市场。

## 上传前自检

运行：

```powershell
tar -tf "C:\Users\Danmiao\.workbuddy\skills\kids-review-editing.zip"
```

确认列表中没有：

- `work/`
- `edl.json`
- `_fc_audio.txt`
- `.env`
- `profile.json`
- `__pycache__/`
- 任何 `*.mp3`、`*.wav`、`*.mp4`、真实转写稿或日期工作目录

只应包含 `assets/icon.png` 这一个图片资产。

## 隐私提醒

这个技能处理儿童学习复盘录音。市场描述和截图不要展示真实儿童姓名、学校、同学姓名、家庭住址或原始录音片段。更多边界见 [PRIVACY.md](PRIVACY.md)。
