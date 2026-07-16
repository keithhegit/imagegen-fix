# 新版Codex生图结果恢复 · Imagegen-Fix

让新版本 Codex即 ChatGPT-Work 客户端 在图片已经生成、但聊天界面没有正常显示时，把隐藏的生图结果恢复出来，保存到工作区，并直接展示给用户。

![Agent Skill](https://img.shields.io/badge/Agent%20Skill-imagegen--result--recovery-blueviolet)
[![GitHub 仓库](https://img.shields.io/badge/GitHub-keithhegit%2Fimagegen--fix-181717?logo=github)](https://github.com/keithhegit/imagegen-fix)
[![安装方式](https://img.shields.io/badge/安装-npx%20skills%20add-2ea44f)](https://skills.sh/)


```text
普通 imagegen 生图
        ↓
Codex 会话中的图片结果
        ↓
恢复 Base64
        ↓
校验图片格式
        ↓
保存到 outputs/
        ↓
在回复中展示图片
```

## 安装给 Agent 用

如果你的 Agent 支持 Skill 安装，直接运行：

```bash
npx skills add keithhegit/imagegen-fix
```

安装后，可以明确告诉 Agent 使用这个技能：

```text
使用 $imagegen-result-recovery 生成并恢复这张图片：一只橙色虎斑猫坐在窗边。
```

也可以在图片已经生成但没有显示时使用：

```text
上一张图片没有显示，请使用 $imagegen-result-recovery 恢复它，不要重新生成。
```

## 什么时候会触发

- 用户明确要求使用这个技能生成并展示图片。
- 用户说刚才生成的图片没有显示。
- 用户询问生成图片保存在哪里。
- 用户要求恢复之前的生图结果或查看原始结果。
- 会话里的图片结果非空，但界面仍显示“生成中”。

## 它不会做什么

- 不会因为界面空白就自动重复调用模型。
- 不会把多兆字节的 Base64 内容直接粘贴到对话中。
- 不会把历史会话里的无关图片导出给用户。
- 不会把“仍在生成”单独当成失败；只要已有可解码的图片结果，就优先恢复。
- 不负责替代普通 `imagegen` 的提示词整理、图片编辑、透明背景和 CLI fallback 策略。

## 工作方式

### 生成后恢复

当用户提出新的生图请求时，先调用普通 `imagegen` 技能。调用返回后，运行恢复脚本查找刚刚生成的结果，完成解码、验证和保存。

### 只恢复已有结果

当用户只是说图片没有显示、想找回图片或想查看之前的结果时，不重新生成。脚本会从最近的 Codex session JSONL 文件中寻找有非空 `result` 的 `image_generation_call`。

### 选择正确的结果

如果同时存在多个生图任务，优先使用图片 ID：

```bash
python scripts/recover_imagegen_result.py \
  --image-id <image-generation-call-id> \
  --out outputs/imagegen-result.png
```

如果没有图片 ID，也可以用刚才提示词中的独特文字筛选：

```bash
python scripts/recover_imagegen_result.py \
  --prompt-contains "橙色虎斑猫" \
  --out outputs/orange-tabby-cat.png
```

已知会话日志时，可以显式指定日志文件：

```bash
python scripts/recover_imagegen_result.py \
  --log <session.jsonl> \
  --out outputs/imagegen-result.png
```

## 校验内容

恢复成功必须同时满足：

1. `payload.result` 是非空 Base64 字符串。
2. Base64 可以成功解码。
3. 解码结果具有 PNG、JPEG、WebP 或 GIF 文件签名。
4. 图片文件成功写入指定位置。

脚本还会输出图片 ID、来源日志、图片格式、字节数和 SHA-256，方便定位结果来源与复核文件完整性。

## 输出位置

默认建议将面向用户的图片保存到当前工作区的 `outputs/` 目录：

```text
outputs/
└── imagegen-result.png
```

如果用户明确要求完整底层响应，可以额外使用 `--raw-json` 保存选中的原始 JSONL 记录。不要把完整 Base64 直接输出到对话中。

## 安全边界

- 恢复模式只读取 Codex session JSONL，不调用外部模型。
- 生成模式仍遵循普通 `imagegen` 技能的内置工具优先规则。
- 恢复失败后不会自动发起第二次生图；只有用户确实需要新图片时，才询问是否重新生成。
- 并发任务较多时，使用 `--image-id`，避免默认选择最近的其他结果。

## 文件结构

```text
imagegen-fix/
├── SKILL.md
├── agents/
│   └── openai.yaml
├── scripts/
│   └── recover_imagegen_result.py
└── README.md
```

## 许可

本仓库当前未附带额外许可证文件。使用、修改或再分发前，请先与仓库作者确认许可范围。

---

<div align="center">

**让已经生成的图片真正回到手里。**

<sub>keithhegit/imagegen-fix</sub>

</div>
