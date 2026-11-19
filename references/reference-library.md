# 项目参考文献库 · Project reference library

Skill 在论文工作目录下自动维护 `.self-learning-academic-writing/references.md`。一个目录可登记多篇论文。Markdown 按文献和章节展示来源、原文副本入口、摘录、可仿写句式及已核对的学习内容。结构化索引和原文副本在同一数据目录内，随项目保留，不进入公开 Git 提交。

同一篇论文换章节或换会话时，继续使用原来的论文工作目录。可以先查看目录，再按当前任务选择合适的文献。每条引文仍需检查原文是否支持稿件中的对应判断。

## 登记并查询

在论文工作目录执行。安装在其他位置时，把脚本路径换成实际安装路径。

```text
python scripts/workflow.py references
python scripts/workflow.py reference-add paper-a --title "论文题名" --file "原文.pdf"
python scripts/workflow.py reference-add paper-b --title "另一篇论文" --doi "10.1234/example" --source "https://doi.org/10.1234/example"
python scripts/workflow.py reference-show paper-a
python scripts/workflow.py reference-show paper-a --section 讨论
```

- `--file` 将用户提供的原文保存到项目资料目录，临时附件路径失效后仍能读取项目副本。相同 DOI 可通过原标识或后加的别名查找；同一原文内容只需保留一份当前副本。
- 只有链接时记录来源。只有文本时，每次 `study` 保存实际读到的章节摘录和全文上下文。需要其他章节而项目内缺少其原文时，再说明缺哪部分。
- `references.md` 由脚本根据索引生成。作者要加入备注时可用 `reference-add {文献标识} --note "备注"`。

## 按章节复用

用原有会话或新会话初始化任务，并指定该次要学习的文献标识。`init` 会报告已复用的章节记录及剩余缺口。已有引言笔记也能按 `Introduction` 找到。写讨论时要从原文读讨论。句式条目列出原文定位、短例句、可填充的句法骨架及适用语境。旧版学习记录没有句式条目时，可以继续使用；需要仿写时，从当前章节的原文副本或已存摘录补录。

```text
python scripts/workflow.py --session next-draft init 讨论 paper-a paper-b
python scripts/workflow.py --session next-draft reuse-study paper-a
```

已读记录和原文附件版本绑定。上传新版本后，新任务只复用适用于该版本的章节记录。旧稿的既有提纲仍按当时的证据保存。需要让当前章节采用新版本时，从项目新副本重读并运行 `study`，更新提纲后重新取得必要的授权。

## English

The skill creates `.self-learning-academic-writing/references.md` in your manuscript workspace. It indexes multiple references, local copies, source excerpts, reusable sentence frames, and section-level reading notes. Keep the same workspace across sessions. Use `references` to open or list the index, `reference-add` to register a source, and `reference-show` to recover its location and notes. Pass a local source with `--file` for reuse after the original upload path disappears. The skill can reuse verified notes for the matching section and file version while keeping your project data local.
