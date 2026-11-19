# 个人写作档案

个人档案是可选的。本机用户可以为每位作者选择不同标识，同一作者在新会话里选择相同标识就能复用偏好。标识可用字母、数字、短横线和下划线。选择与使用档案须获作者允许。

```text
python scripts/workflow.py --session {会话标识} profile-use {作者标识}
python scripts/workflow.py --session {会话标识} profile-show
```

按当前任务筛选偏好。用户当前要求、研究事实与投稿要求优先。偏好只影响写法，具体某篇稿件的模型、数值、结论和当轮修改保留在该项目的章节记录。

当用户明确要求把某种写法记下来时，将其提炼为可复用的偏好条目。输入 JSON 包含唯一的 `key`、规则 `text`、语言 `language`（`zh`、`en` 或 `both`）和可选的 `sections` 章节名列表。空列表表示各章节都适用。示例：

```json
{
  "key": "report-evaluation",
  "text": "比较模型表现时，交代比较对象、指标和验证条件。",
  "language": "both",
  "sections": ["结果", "讨论"]
}
```

```text
python scripts/workflow.py --session {会话标识} profile-propose {偏好.json}
python scripts/workflow.py --session {会话标识} profile-remove {偏好键}
```

向用户展示要写入、更新或删除的具体条目。[授权钩子](agent-hooks.md)通过「保存写作偏好」或「删除写作偏好」记录确认。没有授权钩子时，由用户在同一目录运行 `python scripts/workflow.py --session {会话标识} profile-confirm`，在终端输入相同指令。更新使用原来的 `key`。对成稿的认可属于该任务，偏好保存使用独立确认。

档案默认保存在用户主目录的 `.self-learning-academic-writing/profiles/`，也可通过 `SELF_LEARNING_WRITING_PROFILE_DIR` 使用本机指定目录。稿件和偏好均为本地工作数据，请放在公开发布的 Skill 文件之外。
