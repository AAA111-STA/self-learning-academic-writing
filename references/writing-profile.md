# 写作偏好与个人档案

首次在论文工作目录使用 Skill 时，自动建立 `.self-learning-academic-writing/writing-preferences.md`；同目录的 JSON 是结构化记录。文件只列当前项目已确认的偏好，不把个人档案内容复制进项目。不需要指定文件名或路径，也不会因为某次改稿意见而自动记下一条偏好。

使用 `profile-show` 查看项目记录。只有作者希望把某条习惯带到其他项目时，才选择本机个人档案，然后用 `--scope personal` 查看或更新。个人档案标识可用字母、数字、短横线和下划线；换会话或项目可选择同一标识。

```text
python scripts/workflow.py --session {会话标识} profile-show
python scripts/workflow.py --session {会话标识} profile-use {作者标识}
python scripts/workflow.py --session {会话标识} profile-show --scope personal
```

按当前章节和语言筛选偏好。用户当前要求、研究事实与投稿要求优先，项目偏好优先于个人偏好。具体稿件的模型、数值、结论和当轮修改留在章节记录。

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
python scripts/workflow.py --session {会话标识} profile-propose {偏好.json} --scope personal
python scripts/workflow.py --session {会话标识} profile-remove {偏好键} --scope personal
```

向用户展示具体条目和范围。项目使用「保存写作偏好」或「删除写作偏好」，个人档案使用「保存个人写作偏好」或「删除个人写作偏好」。[授权钩子](agent-hooks.md)从用户消息记录确认；没有钩子时，在同一目录运行 `python scripts/workflow.py --session {会话标识} profile-confirm`，由用户在终端输入相同指令。更新使用原来的 `key`。旧版未标明范围的待确认条目需重新提出。认可成稿不会同时保存偏好。

个人档案仍默认保存在用户主目录的 `.self-learning-academic-writing/profiles/`，也可通过 `SELF_LEARNING_WRITING_PROFILE_DIR` 指定目录。旧版已经确认保存的个人档案无需迁移。稿件和偏好均为本地工作数据，请放在公开发布的 Skill 文件之外。
